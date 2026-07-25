package main

import (
	"bytes"
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"regexp"
	"runtime"
	"sort"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"
)

const serverVersion = "1.0.0"

type BackendHealth struct {
	Available     bool
	Latency       time.Duration
	LastCheck     time.Time
	EMAMsPerToken float64       // Exponential Moving Average of ms per generated token
	TotalTokens   int64         // Total tokens generated (for EMA warmup)
	// Circuit breaker fields
	CircuitState        int       // CircuitClosed, CircuitOpen, CircuitHalfOpen
	ConsecutiveFailures int       // reset on success
	LastFailureTime     time.Time // when circuit tripped to Open
}

// Provider pricing in USD per 1K tokens
type ProviderPricing struct {
	InputPricePer1K  float64 `json:"input_price_per_1k"`
	OutputPricePer1K float64 `json:"output_price_per_1k"`
}

type BrokerServer struct {
	workspaceRoot string
	isCLI         bool
	semaphores    map[string]chan struct{}
	semaphoresMu  sync.Mutex
	healthCache   map[string]BackendHealth
	healthCacheMu sync.RWMutex
	urlOverrides  map[string]string

	// Dynamic pulling state
	pullingStates     map[string]string
	pullingStatesMu   sync.RWMutex
	isPullingActive   bool
	isPullingActiveMu sync.Mutex

	// Warmup cancellation: abort L1 warm-up on first real request
	warmupCancel context.CancelFunc
	warmupDone   chan struct{}

	// Reusable HTTP clients for connection pooling (L4 audit)
	clientFast *http.Client
	clientSlow *http.Client

	// Standalone llama-server process managed by this broker (see
	// llamacpp_provisioner.go). nil when no build has been launched yet.
	llamaCppCmd                 *exec.Cmd
	llamaCppCmdMu               sync.Mutex
	llamaCppLastRelaunchAttempt time.Time
}

func main() {
	workspace := flag.String("workspace", "", "Path to the project workspace root (default: auto-detected)")
	toolName := flag.String("tool", "", "Directly execute tool and exit (CLI mode)")
	toolArgs := flag.String("args", "", "JSON string arguments for direct tool execution")
	httpPort := flag.Int("http-port", 0, "HTTP server port (0 = disabled)")
	flag.Parse()

	rootPath := *workspace
	// If the value looks like an unexpanded template variable (e.g. "${workspaceFolder}"),
	// fall back to auto-detection so the broker doesn't crash with "no such file".
	if rootPath == "" || strings.HasPrefix(rootPath, "${") {
		rootPath = detectWorkspaceRoot()
	}

	fastTransport := &http.Transport{
		MaxIdleConns:        100,
		MaxIdleConnsPerHost: 20,
		IdleConnTimeout:     90 * time.Second,
	}
	slowTransport := &http.Transport{
		MaxIdleConns:        100,
		MaxIdleConnsPerHost: 20,
		IdleConnTimeout:     90 * time.Second,
	}

	srv := &BrokerServer{
		workspaceRoot: rootPath,
		isCLI:         (*toolName != ""),
		semaphores:    make(map[string]chan struct{}),
		healthCache:   make(map[string]BackendHealth),
		pullingStates: make(map[string]string),
		clientFast: &http.Client{
			Transport: fastTransport,
			Timeout:   10 * time.Second, // default timeout for fast ops
		},
		clientSlow: &http.Client{
			Transport: slowTransport,
			Timeout:   300 * time.Second, // default timeout for slow generation
		},
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	if *toolName != "" {
		srv.runCLIMode(ctx, *toolName, *toolArgs)
		return
	}

	fmt.Fprintf(os.Stderr, "mcp-llm-broker: version %s, workspaceRoot: %q\n", serverVersion, rootPath)

	s := server.NewMCPServer("mcp-llm-broker", serverVersion)

	// Tool Registration
	s.AddTool(mcp.NewTool(
		"detect_backends",
		mcp.WithDescription("Detect active local LLM backends (Ollama, Jan, LM Studio) and environment context (WSL, Kubernetes)."),
	), srv.handleDetectBackends)

	s.AddTool(mcp.NewTool(
		"get_routing_decision",
		mcp.WithDescription("Calculate prompt complexity score and get the optimal local/cloud LLM routing decision."),
		mcp.WithString("task_description", mcp.Required(), mcp.Description("The description of the task to analyze")),
	), srv.handleGetRoutingDecision)

	s.AddTool(mcp.NewTool(
		"execute_prompt",
		mcp.WithDescription("Execute an LLM prompt by automatically routing it to the optimal local or cloud backend."),
		mcp.WithString("prompt", mcp.Required(), mcp.Description("The prompt to send to the model")),
		mcp.WithString("system_prompt", mcp.Description("Optional system instructions")),
		mcp.WithString("difficulty_hint", mcp.Description("Optional description of the task to calculate complexity / route")),
		mcp.WithString("model", mcp.Description("Optional specific model to execute (overrides routing)")),
		mcp.WithString("json_schema", mcp.Description("Optional JSON Schema to enforce structured output (e.g., '{\"type\": \"object\", \"properties\": {\"name\": {\"type\": \"string\"}}}')")),
		mcp.WithString("stream", mcp.Description("Optional: set to 'true' to enable streaming output")),
	), srv.handleExecutePrompt)

	s.AddTool(mcp.NewTool(
		"call_agent",
		mcp.WithDescription(srv.buildCallAgentDescription()),
		mcp.WithString("agent_name", mcp.Required(), mcp.Description("Exact agent name from the available list. Never use 'orchestrator'.")),
		mcp.WithString("task", mcp.Required(), mcp.Description("The task or question to send to the agent")),
		mcp.WithString("tier", mcp.Description("Optional tier override: L1, L2, L3, L4")),
	), srv.handleCallAgent)

	s.AddTool(mcp.NewTool(
		"provision_llamacpp",
		mcp.WithDescription("Build (if not already built) and launch a standalone llama-server "+
			"instance managed by this broker, auto-selecting one of Jan's already-downloaded "+
			".gguf models for the given tier and self-writing the resolved URL into "+
			"router_rules.json. The first build compiles llama.cpp from source (several minutes "+
			"of CPU time) — call this explicitly; it is not triggered automatically. Once built, "+
			"the health-check loop auto-relaunches the same binary if the process later dies."),
		mcp.WithString("tier", mcp.Description("Model tier to launch: L1, L2, L3, or L4. Defaults to L3 if omitted.")),
	), srv.handleProvisionLlamaCpp)

	if *toolName == "" {
		go srv.startHealthCheckLoop(ctx)
	}

	if *httpPort > 0 {
		srv.startWithHTTP(ctx, s, *httpPort)
	} else {
		server.ServeStdio(s)
	}
}

// startWithHTTP starts the HTTP server and MCP stdio, handling port conflicts by
// evicting any stale process that holds the port before retrying.
func (b *BrokerServer) startWithHTTP(ctx context.Context, s *server.MCPServer, port int) {
	httpSrv := b.createHTTPServer(port)

	// Graceful shutdown goroutine: drain in-flight requests on ctx.Done.
	go func() {
		<-ctx.Done()
		drainCtx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
		defer cancel()
		fmt.Fprintf(os.Stderr, "mcp-llm-broker: shutting down HTTP server (30s drain)...\n")
		if err := httpSrv.Shutdown(drainCtx); err != nil {
			fmt.Fprintf(os.Stderr, "mcp-llm-broker: HTTP shutdown error: %v\n", err)
		}
	}()

	tryHTTP := func() (started bool) {
		errCh := make(chan error, 1)
		go func() {
			fmt.Fprintf(os.Stderr, "mcp-llm-broker: HTTP server listening on %s\n", httpSrv.Addr)
			errCh <- httpSrv.ListenAndServe()
		}()

		select {
		case err := <-errCh:
			if err != nil && err != http.ErrServerClosed {
				if strings.Contains(err.Error(), "address already in use") {
					return false // caller will evict and retry
				}
				fmt.Fprintf(os.Stderr, "mcp-llm-broker: HTTP server error: %v\n", err)
				os.Exit(1)
			}
			return true
		case <-time.After(200 * time.Millisecond):
			// HTTP bound successfully — serve stdio in the background, block until shutdown
			go server.ServeStdio(s)
			<-ctx.Done() // block until signal received
			return true
		}
	}

	if !tryHTTP() {
		// Port in use. This machine can have several independent
		// mcp-llm-broker processes wanting the same hardcoded port at once
		// (one per Claude Code / opencode session) — the occupant is far
		// more likely to be another session's live instance than a truly
		// stale one. Only evict if it fails a liveness check; otherwise
		// leave it running and degrade to stdio-only, same as the "still in
		// use after eviction" path below. Killing a live occupant used to
		// sever whatever MCP session depended on it with no warning.
		if isBrokerAlive(port) {
			fmt.Fprintf(os.Stderr, "mcp-llm-broker: port %d in use by a healthy instance — not evicting, stdio-only\n", port)
		} else {
			fmt.Fprintf(os.Stderr, "mcp-llm-broker: port %d in use by an unresponsive instance — evicting\n", port)
			killProcessOnPort(port)
			time.Sleep(300 * time.Millisecond)

			if !tryHTTP() {
				// Still in use — degrade to stdio-only so opencode at least gets MCP tools
				fmt.Fprintf(os.Stderr, "mcp-llm-broker: port %d still in use after eviction — stdio-only\n", port)
			}
		}
	}
	// Reached only in the stdio-only fallback path
	server.ServeStdio(s)
}

// isBrokerAlive reports whether a healthy mcp-llm-broker instance is already
// answering on port — a fast /healthz probe, not just "is the port open".
// A short timeout keeps this from stalling startup: an occupant that can't
// answer within it is treated the same as one that isn't there at all.
func isBrokerAlive(port int) bool {
	client := http.Client{Timeout: 500 * time.Millisecond}
	resp, err := client.Get(fmt.Sprintf("http://127.0.0.1:%d/healthz", port))
	if err != nil {
		return false
	}
	defer resp.Body.Close()
	return resp.StatusCode == http.StatusOK
}

// killProcessOnPort sends SIGTERM to whatever process holds the given TCP
// port. Only called after isBrokerAlive has already returned false — see
// startWithHTTP.
func killProcessOnPort(port int) {
	// Try fuser first (available on most Linux/WSL systems)
	if err := exec.Command("fuser", "-k", fmt.Sprintf("%d/tcp", port)).Run(); err == nil {
		return
	}
	// Fallback: parse /proc/net/tcp* for the inode, then find matching PID in /proc
	if pid := findPIDByPort(port); pid > 0 {
		if p, err := os.FindProcess(pid); err == nil {
			_ = p.Signal(syscall.SIGTERM)
		}
	}
}

// findPIDByPort returns the PID of the process listening on the given TCP port,
// by parsing /proc/net/tcp and /proc/net/tcp6 on Linux.
func findPIDByPort(port int) int {
	hexPort := fmt.Sprintf("%04X", port)
	inode := ""
	for _, f := range []string{"/proc/net/tcp", "/proc/net/tcp6"} {
		data, err := os.ReadFile(f)
		if err != nil {
			continue
		}
		for _, line := range strings.Split(string(data), "\n")[1:] {
			fields := strings.Fields(line)
			if len(fields) < 10 {
				continue
			}
			// local_address field is "hexIP:hexPort"
			parts := strings.Split(fields[1], ":")
			if len(parts) == 2 && strings.EqualFold(parts[1], hexPort) && fields[3] == "0A" { // 0A = LISTEN
				inode = fields[9]
				break
			}
		}
		if inode != "" {
			break
		}
	}
	if inode == "" {
		return 0
	}
	// Walk /proc/<pid>/fd/* looking for a socket with that inode
	target := "socket:[" + inode + "]"
	entries, _ := os.ReadDir("/proc")
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		pid := 0
		if _, err := fmt.Sscanf(e.Name(), "%d", &pid); err != nil || pid <= 0 {
			continue
		}
		fds, _ := os.ReadDir(fmt.Sprintf("/proc/%d/fd", pid))
		for _, fd := range fds {
			link, err := os.Readlink(fmt.Sprintf("/proc/%d/fd/%s", pid, fd.Name()))
			if err == nil && link == target {
				return pid
			}
		}
	}
	return 0
}

func (b *BrokerServer) runCLIMode(ctx context.Context, tool string, argsJSON string) {
	var args map[string]interface{}
	if argsJSON != "" {
		if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
			fmt.Fprintf(os.Stderr, "Error parsing JSON args: %v\n", err)
			os.Exit(1)
		}
	} else {
		args = make(map[string]interface{})
	}

	req := mcp.CallToolRequest{
		Request: mcp.Request{
			Method: "tools/call",
		},
		Params: mcp.CallToolParams{
			Name:      tool,
			Arguments: args,
		},
	}

	var res *mcp.CallToolResult
	var err error

	switch tool {
	case "detect_backends":
		res, err = b.handleDetectBackends(ctx, req)
	case "get_routing_decision":
		res, err = b.handleGetRoutingDecision(ctx, req)
	case "execute_prompt":
		res, err = b.handleExecutePrompt(ctx, req)
	case "call_agent":
		res, err = b.handleCallAgent(ctx, req)
	case "provision_llamacpp":
		res, err = b.handleProvisionLlamaCpp(ctx, req)
	default:
		fmt.Fprintf(os.Stderr, "Unknown tool: %s\n", tool)
		os.Exit(1)
	}

	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}

	if res.IsError {
		for _, c := range res.Content {
			if txt, ok := c.(mcp.TextContent); ok {
				fmt.Println(txt.Text)
			}
		}
		os.Exit(1)
	}

	for _, c := range res.Content {
		if txt, ok := c.(mcp.TextContent); ok {
			fmt.Println(txt.Text)
		}
	}
}

func (b *BrokerServer) handleGetRoutingDecision(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	taskDesc, _ := req.RequireString("task_description")

	// Detect pulled models from local backends
	pulled := make(map[string]string)
	env := b.detectEnv()

	discoverCtx, cancel := context.WithTimeout(ctx, 3*time.Second)
	defer cancel()

	// Gather models from Ollama
	ollamaURL := b.getOllamaURL(env)
	if models, err := b.fetchOllamaModels(discoverCtx, ollamaURL); err == nil {
		for _, m := range models {
			pulled[m] = ProviderOllama
		}
	}

	// Gather models from Jan (with WSL gateway fallback)
	if models, err := b.fetchOpenAICompatibleModels(discoverCtx, DefaultJanURL); err == nil {
		for _, m := range models {
			pulled[m] = ProviderJan
		}
	} else if env.IsWSL && env.WSLGateway != "" {
		wslURL := fmt.Sprintf("http://%s:1337", env.WSLGateway)
		if models, err := b.fetchOpenAICompatibleModels(discoverCtx, wslURL); err == nil {
			for _, m := range models {
				pulled[m] = ProviderJan
			}
		}
	}

	// Gather models from LM Studio (with WSL gateway fallback)
	if models, err := b.fetchOpenAICompatibleModels(discoverCtx, DefaultLMStudioURL); err == nil {
		for _, m := range models {
			pulled[m] = ProviderLMStudio
		}
	} else if env.IsWSL && env.WSLGateway != "" {
		wslURL := fmt.Sprintf("http://%s:1234", env.WSLGateway)
		if models, err := b.fetchOpenAICompatibleModels(discoverCtx, wslURL); err == nil {
			for _, m := range models {
				pulled[m] = ProviderLMStudio
			}
		}
	}

	// Gather models from a standalone llama-server — URL is user-configured
	// (random port), not guessed via WSL-gateway fallback like the providers above.
	llamaCppURL := DefaultLlamaCppURL
	if rules, err := b.loadRules(); err == nil && rules.LlamaCppBaseURL != "" {
		llamaCppURL = rules.LlamaCppBaseURL
	}
	if models, err := b.fetchOpenAICompatibleModels(discoverCtx, llamaCppURL); err == nil {
		for _, m := range models {
			pulled[m] = ProviderLlamaCpp
		}
	}

	decision, err := b.makeRoutingDecision(taskDesc, pulled, "")
	if err != nil {
		return mcp.NewToolResultError("failed to make routing decision: " + err.Error()), nil
	}

	jsonData, err := json.MarshalIndent(decision, "", "  ")
	if err != nil {
		return mcp.NewToolResultError("failed to marshal routing decision: " + err.Error()), nil
	}

	return mcp.NewToolResultText(string(jsonData)), nil
}

// detectWorkspaceRoot searches upwards from current working directory or executable path for a folder containing .agent
func detectWorkspaceRoot() string {
	// 1. Try working directory
	cwd, err := os.Getwd()
	if err == nil {
		dir := cwd
		for {
			agentDir := filepath.Join(dir, ".agent")
			if stat, err := os.Stat(agentDir); err == nil && stat.IsDir() {
				return dir
			}

			parent := filepath.Dir(dir)
			if parent == dir {
				break
			}
			dir = parent
		}
	}

	// 2. Try executable path
	execPath, err := os.Executable()
	if err == nil {
		dir := filepath.Dir(execPath)
		for {
			agentDir := filepath.Join(dir, ".agent")
			if stat, err := os.Stat(agentDir); err == nil && stat.IsDir() {
				return dir
			}

			parent := filepath.Dir(dir)
			if parent == dir {
				break
			}
			dir = parent
		}
	}

	return "."
}

// Structs for Discovery Tool
type OllamaModel struct {
	Name string `json:"name"`
}

type OllamaTagsResponse struct {
	Models []OllamaModel `json:"models"`
}

type OpenAIModel struct {
	ID string `json:"id"`
}

type OpenAIModelsResponse struct {
	Data []OpenAIModel `json:"data"`
}

type BackendInfo struct {
	Name      string   `json:"name"`
	URL       string   `json:"url"`
	Available bool     `json:"available"`
	Models    []string `json:"models,omitempty"`
	Error     string   `json:"error,omitempty"`
}

type EnvironmentInfo struct {
	OS          string `json:"os"`
	IsWSL       bool   `json:"is_wsl"`
	IsContainer bool   `json:"is_container"`
	IsK8s       bool   `json:"is_k8s"`
	WSLGateway  string `json:"wsl_gateway,omitempty"`
}

type DiscoveryResult struct {
	Environment EnvironmentInfo   `json:"environment"`
	Backends    []BackendInfo     `json:"backends"`
	Downloads   map[string]string `json:"active_downloads,omitempty"`
}

// checkOpenAIWithWSLFallback tries the given default URL first, then falls back
// to the WSL gateway (Windows host) if we're inside WSL and localhost fails.
func (b *BrokerServer) checkOpenAIWithWSLFallback(ctx context.Context, name, defaultURL, port string, env EnvironmentInfo) BackendInfo {
	backend := BackendInfo{Name: name, URL: defaultURL}

	// Try localhost first with a short timeout
	localCtx, localCancel := context.WithTimeout(ctx, 800*time.Millisecond)
	models, err := b.fetchOpenAICompatibleModels(localCtx, defaultURL)
	localCancel()
	if err == nil {
		backend.Available = true
		backend.Models = models
		return backend
	}

	// If WSL and localhost failed, try the Windows host via WSL gateway
	if env.IsWSL && env.WSLGateway != "" {
		wslURL := fmt.Sprintf("http://%s:%s", env.WSLGateway, port)
		backend.URL = wslURL
		wslCtx, wslCancel := context.WithTimeout(ctx, 1200*time.Millisecond)
		models, err = b.fetchOpenAICompatibleModels(wslCtx, wslURL)
		wslCancel()
		if err == nil {
			backend.Available = true
			backend.Models = models
			backend.Error = "" // clear the localhost error
			return backend
		}
	}

	backend.Available = false
	backend.Error = err.Error()
	return backend
}

// checkOllamaWithWSLFallback tries localhost first, then WSL gateway for Ollama.
func (b *BrokerServer) checkOllamaWithWSLFallback(ctx context.Context, env EnvironmentInfo) BackendInfo {
	ollamaURL := b.getOllamaURL(env)
	backend := BackendInfo{Name: "Ollama", URL: ollamaURL}

	localCtx, localCancel := context.WithTimeout(ctx, 800*time.Millisecond)
	models, err := b.fetchOllamaModels(localCtx, ollamaURL)
	localCancel()
	if err == nil {
		backend.Available = true
		backend.Models = models
		return backend
	}

	// If WSL and getOllamaURL already returned localhost, try the gateway explicitly
	if env.IsWSL && env.WSLGateway != "" && ollamaURL == DefaultOllamaURL {
		wslURL := fmt.Sprintf("http://%s:%s", env.WSLGateway, OllamaDefaultPortStr)
		wslCtx, wslCancel := context.WithTimeout(ctx, 1200*time.Millisecond)
		models, err = b.fetchOllamaModels(wslCtx, wslURL)
		wslCancel()
		if err == nil {
			backend.URL = wslURL
			backend.Available = true
			backend.Models = models
			return backend
		}
	}

	backend.Available = false
	backend.Error = err.Error()
	return backend
}

// handleDetectBackends checks availability of local LLM providers and lists their models.
func (b *BrokerServer) handleDetectBackends(ctx context.Context, _ mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	env := b.detectEnv()
	result := DiscoveryResult{
		Environment: env,
	}

	// 1. Ollama Check (with WSL gateway fallback) - use fresh context with dedicated timeout
	ollamaCtx, ollamaCancel := context.WithTimeout(ctx, 2*time.Second)
	result.Backends = append(result.Backends, b.checkOllamaWithWSLFallback(ollamaCtx, env))
	ollamaCancel()

	// 2. Jan Check (with WSL gateway fallback) - use fresh context with dedicated timeout
	janCtx, janCancel := context.WithTimeout(ctx, 2*time.Second)
	result.Backends = append(result.Backends, b.checkOpenAIWithWSLFallback(janCtx, "Jan", DefaultJanURL, "1337", env))
	janCancel()

	// 3. LM Studio Check (with WSL gateway fallback) - use fresh context with dedicated timeout
	lmsCtx, lmsCancel := context.WithTimeout(ctx, 2*time.Second)
	result.Backends = append(result.Backends, b.checkOpenAIWithWSLFallback(lmsCtx, "LM Studio", DefaultLMStudioURL, "1234", env))
	lmsCancel()

	// 4. Standalone llama-server check — no WSL-gateway fallback: the configured
	// URL is already the fully-resolved address the user set after starting
	// llama-server on its (random) port, so there is no fixed port to guess from.
	llamaCppURL := DefaultLlamaCppURL
	if rules, err := b.loadRules(); err == nil && rules.LlamaCppBaseURL != "" {
		llamaCppURL = rules.LlamaCppBaseURL
	}
	llamaCppCtx, llamaCppCancel := context.WithTimeout(ctx, 2*time.Second)
	llamaCppBackend := BackendInfo{Name: "llama.cpp", URL: llamaCppURL}
	if models, err := b.fetchOpenAICompatibleModels(llamaCppCtx, llamaCppURL); err == nil {
		llamaCppBackend.Available = true
		llamaCppBackend.Models = models
	} else {
		llamaCppBackend.Available = false
		llamaCppBackend.Error = err.Error()
	}
	llamaCppCancel()
	result.Backends = append(result.Backends, llamaCppBackend)

	b.pullingStatesMu.RLock()
	if len(b.pullingStates) > 0 {
		result.Downloads = make(map[string]string)
		for k, v := range b.pullingStates {
			result.Downloads[k] = v
		}
	}
	b.pullingStatesMu.RUnlock()

	jsonData, err := json.MarshalIndent(result, "", "  ")
	if err != nil {
		return mcp.NewToolResultError("failed to marshal discovery results: " + err.Error()), nil
	}

	return mcp.NewToolResultText(string(jsonData)), nil
}

func (b *BrokerServer) detectEnv() EnvironmentInfo {
	env := EnvironmentInfo{
		OS: runtime.GOOS,
	}

	// WSL Detection
	if data, err := os.ReadFile("/proc/version"); err == nil {
		if strings.Contains(strings.ToLower(string(data)), "microsoft") ||
			strings.Contains(strings.ToLower(string(data)), "wsl") {
			env.IsWSL = true
			env.WSLGateway = b.getWSLGateway()
		}
	}

	// Container Detection (Docker, Podman, containerd)
	if _, err := os.Stat("/.dockerenv"); err == nil {
		env.IsContainer = true
	} else if data, err := os.ReadFile("/proc/1/cgroup"); err == nil {
		if strings.Contains(string(data), "docker") ||
			strings.Contains(string(data), "containerd") ||
			strings.Contains(string(data), "podman") ||
			strings.Contains(string(data), "buildkit") {
			env.IsContainer = true
		}
	}

	// K8s Detection
	if os.Getenv("KUBERNETES_SERVICE_HOST") != "" {
		env.IsK8s = true
		env.IsContainer = true
	} else if _, err := os.Stat("/var/run/secrets/kubernetes.io"); err == nil {
		env.IsK8s = true
		env.IsContainer = true
	}

	return env
}

func (b *BrokerServer) getWSLGateway() string {
	// Priority 1: default gateway from ip route (WSL host in WSL2)
	routeData, err := os.ReadFile("/proc/net/route")
	if err == nil {
		lines := strings.Split(string(routeData), "\n")
		for _, line := range lines[1:] { // skip header
			fields := strings.Fields(line)
			if len(fields) >= 3 && fields[1] == "00000000" { // destination 0.0.0.0
				if len(fields[2]) == 8 {
					gw := fmt.Sprintf("%d.%d.%d.%d",
						hexToByte(fields[2][6:8]),
						hexToByte(fields[2][4:6]),
						hexToByte(fields[2][2:4]),
						hexToByte(fields[2][0:2]),
					)
					if gw != "0.0.0.0" {
						return gw
					}
				}
			}
		}
	}

	// Priority 2: resolvectl / systemd-resolved
	if data, err := os.ReadFile("/etc/resolv.conf"); err == nil {
		lines := strings.Split(string(data), "\n")
		for _, line := range lines {
			if strings.HasPrefix(line, "nameserver") {
				parts := strings.Fields(line)
				if len(parts) >= 2 {
					ns := parts[1]
					// Skip loopback and typical router IPs — they are not the WSL host
					if ns == "127.0.0.1" || ns == "127.0.0.53" || ns == "1.1.1.1" || ns == "8.8.8.8" {
						continue
					}
					return ns
				}
			}
		}
	}

	return ""
}

// hexToByte converts a hex string (00-ff) to a byte value.
func hexToByte(h string) byte {
	if len(h) < 2 {
		return 0
	}
	val := 0
	for i := 0; i < 2; i++ {
		c := h[i]
		switch {
		case c >= '0' && c <= '9':
			val = val*16 + int(c-'0')
		case c >= 'a' && c <= 'f':
			val = val*16 + int(c-'a'+10)
		case c >= 'A' && c <= 'F':
			val = val*16 + int(c-'A'+10)
		}
	}
	return byte(val)
}

func (b *BrokerServer) getOllamaURL(env EnvironmentInfo) string {
	if host := os.Getenv("OLLAMA_HOST"); host != "" {
		if !strings.HasPrefix(host, "http://") && !strings.HasPrefix(host, "https://") {
			host = "http://" + host
		}
		return strings.TrimSuffix(host, "/")
	}

	defaultURL := DefaultOllamaURL

	if env.IsWSL && env.WSLGateway != "" {
		client := &http.Client{Timeout: 1500 * time.Millisecond}
		resp, err := client.Get(DefaultOllamaURL + "/api/tags")
		if err == nil {
			resp.Body.Close()
			return defaultURL
		}
		wslURL := fmt.Sprintf("http://%s:%s", env.WSLGateway, OllamaDefaultPortStr)
		resp, err = client.Get(wslURL + "/api/tags")
		if err == nil {
			resp.Body.Close()
			return wslURL
		}
	}

	return defaultURL
}

func (b *BrokerServer) fetchOllamaModels(ctx context.Context, baseURL string) ([]string, error) {
	url := fmt.Sprintf("%s/api/tags", baseURL)
	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return nil, err
	}
	client := b.clientFast
	if client == nil {
		client = &http.Client{Timeout: 10 * time.Second}
	}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("status code %d", resp.StatusCode)
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	var tagsResp OllamaTagsResponse
	if err := json.Unmarshal(body, &tagsResp); err != nil {
		return nil, err
	}

	var models []string
	for _, m := range tagsResp.Models {
		models = append(models, m.Name)
	}
	return models, nil
}

func (b *BrokerServer) fetchOpenAICompatibleModels(ctx context.Context, baseURL string) ([]string, error) {
	url := fmt.Sprintf("%s/v1/models", baseURL)
	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return nil, err
	}
	client := b.clientFast
	if client == nil {
		client = &http.Client{Timeout: 10 * time.Second}
	}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("status code %d", resp.StatusCode)
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	var modelsResp OpenAIModelsResponse
	if err := json.Unmarshal(body, &modelsResp); err != nil {
		return nil, err
	}

	var models []string
	for _, m := range modelsResp.Data {
		models = append(models, m.ID)
	}
	return models, nil
}

func (b *BrokerServer) checkAllHealth(ctx context.Context) {
	env := b.detectEnv()

	llamaCppURL := DefaultLlamaCppURL
	if rules, err := b.loadRules(); err == nil && rules.LlamaCppBaseURL != "" {
		llamaCppURL = rules.LlamaCppBaseURL
	}

	providers := []struct {
		name     string
		url      string
		isOllama bool
		wslPort  string // empty means "no WSL-gateway fallback for this provider"
	}{
		{ProviderOllama, b.getOllamaURL(env), true, OllamaDefaultPortStr},
		{ProviderJan, DefaultJanURL, false, "1337"},
		{ProviderLMStudio, DefaultLMStudioURL, false, "1234"},
		// llama-server's URL is already the fully-resolved, user-configured address
		// (random port) — there is no fixed default port to guess a WSL-gateway
		// fallback from, so wslPort is intentionally left empty.
		{ProviderLlamaCpp, llamaCppURL, false, ""},
	}

	for _, p := range providers {
		start := time.Now()
		var err error

		// Try localhost first with a dedicated 800ms timeout context
		localCtx, localCancel := context.WithTimeout(ctx, 800*time.Millisecond)
		if p.isOllama {
			_, err = b.fetchOllamaModels(localCtx, p.url)
		} else {
			_, err = b.fetchOpenAICompatibleModels(localCtx, p.url)
		}
		localCancel()

		// If localhost failed and we're in WSL, try the WSL gateway with a fresh timeout context
		if err != nil && p.wslPort != "" && env.IsWSL && env.WSLGateway != "" {
			wslURL := fmt.Sprintf("http://%s:%s", env.WSLGateway, p.wslPort)
			wslCtx, wslCancel := context.WithTimeout(ctx, 1200*time.Millisecond)
			if p.isOllama {
				var mErr error
				_, mErr = b.fetchOllamaModels(wslCtx, wslURL)
				if mErr == nil {
					err = nil
				}
			} else {
				_, mErr := b.fetchOpenAICompatibleModels(wslCtx, wslURL)
				if mErr == nil {
					err = nil
				}
			}
			wslCancel()
		}

		duration := time.Since(start)

		b.healthCacheMu.Lock()
		b.healthCache[p.name] = mergeHealthCheckResult(b.healthCache[p.name], err == nil, duration)
		b.healthCacheMu.Unlock()

		if p.name == ProviderLlamaCpp && err != nil {
			// Only relaunches an already-built binary (rate-limited); never
			// triggers the first, heavy source build automatically.
			b.maybeAutoRelaunchLlamaCpp(ctx)
		}
	}
}

// mergeHealthCheckResult applies a periodic health-probe result on top of the
// existing BackendHealth entry, preserving fields that only real request outcomes
// should update (CircuitState, ConsecutiveFailures, LastFailureTime, EMA latency
// stats). A full-struct overwrite here would silently reset an OPEN circuit breaker
// back to Closed on the next health tick, even though the periodic probe only ever
// checks a lightweight metadata endpoint (e.g. /v1/models) — never the actual
// completion path that recordProviderFailure/recordProviderSuccess react to.
func mergeHealthCheckResult(existing BackendHealth, available bool, latency time.Duration) BackendHealth {
	existing.Available = available
	existing.Latency = latency
	existing.LastCheck = time.Now()
	return existing
}

func (b *BrokerServer) startHealthCheckLoop(ctx context.Context) {
	// Do initial check
	b.checkAllHealth(ctx)

	// Pre-load the L1 model so it's warm in Jan's memory before the first user request.
	// Without this, the first inference waits 30–60 s for model loading + generation.
	// The warmup is cancellable: executePromptLogic cancels it on first real request
	// to avoid blocking the Jan semaphore.
	warmupCtx, warmupCancel := context.WithCancel(ctx)
	b.warmupCancel = warmupCancel
	b.warmupDone = make(chan struct{})
	go b.warmUpJanL1(warmupCtx)

	ticker := time.NewTicker(20 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			b.checkAllHealth(ctx)
		}
	}
}

// warmUpJanL1 sends a minimal (1-token) request to the configured L1 model so Jan
// loads it into GPU memory before the first real user request arrives.
// The request deliberately uses NO system prompt so it pre-loads the "no system"
// llamacpp instance — the same instance all real L1 requests will use (system prompts
// are stripped in tryStreamDirect to avoid Jan spawning a separate slow process).
func (b *BrokerServer) warmUpJanL1(ctx context.Context) {
	defer func() {
		if b.warmupDone != nil {
			close(b.warmupDone)
		}
	}()

	// Small initial delay so Jan finishes its own startup sequence.
	select {
	case <-time.After(5 * time.Second):
	case <-ctx.Done():
		fmt.Fprintf(os.Stderr, "[INFO] warmup: cancelled before start\n")
		return
	}

	rules, err := b.loadRules()
	if err != nil {
		fmt.Fprintf(os.Stderr, "[WARN] warmup: cannot load rules: %v\n", err)
		return
	}

	// Resolve the L1 model name from the "jan" provider block.
	l1Model := ""
	if janBlock, ok := rules.Models[ProviderJan]; ok {
		if v, ok := janBlock["L1"]; ok {
			if s, ok := v.(string); ok {
				l1Model = s
			}
		}
	}
	if l1Model == "" {
		fmt.Fprintf(os.Stderr, "[WARN] warmup: no Jan L1 model configured\n")
		return
	}

	// Detect Jan URL (with WSL gateway fallback).
	env := b.detectEnv()
	discoverCtx, cancel := context.WithTimeout(ctx, 2*time.Second)
	defer cancel()
	var janURL string
	if _, err := b.fetchOpenAICompatibleModels(discoverCtx, DefaultJanURL); err == nil {
		janURL = DefaultJanURL
	} else if env.IsWSL && env.WSLGateway != "" {
		wslURL := fmt.Sprintf("http://%s:1337", env.WSLGateway)
		if _, err := b.fetchOpenAICompatibleModels(discoverCtx, wslURL); err == nil {
			janURL = wslURL
		}
	}
	if janURL == "" {
		fmt.Fprintf(os.Stderr, "[WARN] warmup: Jan not reachable — skipping warm-up\n")
		return
	}

	fmt.Fprintf(os.Stderr, "[INFO] warmup: loading %s into Jan memory (%s)...\n", l1Model, janURL)

	// Use Anthropic /messages — avoids spawning a new llamacpp process on Jan.
	payload := map[string]any{
		"model":      l1Model,
		"messages":   []map[string]any{{"role": "user", "content": "hi"}},
		"max_tokens": 1,
		"stream":     false,
	}
	data, err := json.Marshal(payload)
	if err != nil {
		return
	}

	warmupCtx, cancel := context.WithTimeout(ctx, 120*time.Second)
	defer cancel()

	req, err := http.NewRequestWithContext(warmupCtx, "POST",
		fmt.Sprintf("%s/messages", janURL), bytes.NewReader(data))
	if err != nil {
		return
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("anthropic-version", "2023-06-01")

	resp, err := (&http.Client{Timeout: 120 * time.Second}).Do(req)
	if err != nil {
		fmt.Fprintf(os.Stderr, "[WARN] warmup: %s load failed: %v\n", l1Model, err)
		return
	}
	defer resp.Body.Close()
	io.ReadAll(resp.Body) // drain
	fmt.Fprintf(os.Stderr, "[INFO] warmup: %s loaded (HTTP %d)\n", l1Model, resp.StatusCode)
}


// agentEntry is one discovered agent — name and description parsed straight
// from its .md frontmatter.
type agentEntry struct {
	Name        string
	Description string
}

var (
	agentFrontmatterNameRe = regexp.MustCompile(`(?m)^name:\s*(.+)$`)
	agentFrontmatterDescRe = regexp.MustCompile(`(?m)^description:\s*(.+)$`)
)

// parseAgentFrontmatter extracts name:/description: from a single-line YAML
// frontmatter block. The block is bounded the same way sync_agents.py's
// parse_frontmatter() bounds it — the closing delimiter must be a line
// starting at column 0 — rather than the first bare occurrence of "---"
// anywhere in the content. A blind search breaks the instant an earlier line
// contains "---", e.g. a YAML comment inside a nested list (real example:
// cto.md has "# --- Squad Leads (primary routing layer) ---" inside its
// delegates_to block; see this task's history for the same bug hitting
// sync_agents.py's Python-side parser and the fix applied there).
func parseAgentFrontmatter(content string) (name, description string) {
	if !strings.HasPrefix(content, "---") {
		return "", ""
	}
	end := strings.Index(content[3:], "\n---")
	if end == -1 {
		return "", ""
	}
	block := content[3 : 3+end]

	if m := agentFrontmatterNameRe.FindStringSubmatch(block); m != nil {
		name = strings.TrimSpace(m[1])
	}
	if m := agentFrontmatterDescRe.FindStringSubmatch(block); m != nil {
		description = strings.TrimSpace(m[1])
	}
	return name, description
}

// loadAgentList scans .agent/agents/**/*.md directly — the source tree with
// exactly one file per real specialist/management-tier agent persona — and
// extracts each one's name/description straight from its frontmatter.
//
// This used to parse the Agents table out of .agent/ARCHITECTURE.md instead,
// which silently dropped any agent added without a matching table row (the
// entire management/ squad-lead/C-level tier was unreachable via call_agent —
// see tasks/2026-07-25-mcp-llm-broker-call-agent-drops-management-tier-agents.md).
// An intermediate design read a separate compiled+schema-validated
// agent_registry.json manifest instead of scanning live; that manifest was
// removed as unneeded machinery once weighed against the actual trust model
// here — .agent/agents/ is committed repo content, not attacker-supplied
// input, and invokeAgent() below already reads a single such file's full body
// and trusts it completely as the system prompt, so treating this narrower
// name+description read as the higher-risk operation didn't hold up. Schema
// validation of every agent's frontmatter still runs — as a CI-time check in
// sync_agents.py — it just no longer gates what this function reads at
// runtime, so a data-quality issue in one agent's file can never make a
// *different*, well-formed agent uncallable.
//
// Deliberately does NOT include .claude/agents/ — that directory also carries
// workflow-derived pseudo-agents (wf-*.md, synthesized from
// .agent/workflows/) that were never part of ARCHITECTURE.md's Agents table
// either; scanning only the source tree keeps this list's scope identical to
// what it always documented.
//
// Returns agent entries excluding "orchestrator" (which must never be delegated to).
func (b *BrokerServer) loadAgentList() []agentEntry {
	agentsRoot := filepath.Join(b.workspaceRoot, ".agent", "agents")

	var entries []agentEntry
	_ = filepath.Walk(agentsRoot, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() || !strings.HasSuffix(path, ".md") {
			return nil
		}
		data, rErr := os.ReadFile(path)
		if rErr != nil {
			return nil
		}
		name, description := parseAgentFrontmatter(string(data))
		if name == "" {
			name = strings.TrimSuffix(filepath.Base(path), ".md")
		}
		if name == "" || name == "orchestrator" {
			return nil
		}
		entries = append(entries, agentEntry{Name: name, Description: description})
		return nil
	})

	sort.Slice(entries, func(i, j int) bool { return entries[i].Name < entries[j].Name })
	return entries
}

// buildCallAgentDescription builds the call_agent tool description from the live agent list.
func (b *BrokerServer) buildCallAgentDescription() string {
	entries := b.loadAgentList()
	base := "Invoke a specialist sub-agent. Loads the agent's system prompt from .claude/agents/<name>.md and executes the task with that persona. ONLY use names from this list — do not invent agent names or tools."
	if len(entries) == 0 {
		return base
	}
	var names []string
	for _, e := range entries {
		names = append(names, fmt.Sprintf("%s (%s)", e.Name, e.Description))
	}
	return base + " Available agents: " + strings.Join(names, "; ") + "."
}

// invokeAgent loads a specialist agent's system prompt and executes a task with it.
// Shared by handleCallAgent (MCP tool) and the internal agentic loop.
func (b *BrokerServer) invokeAgent(ctx context.Context, agentName, task, tierOverride string) (*ExecutionResult, error) {
	if agentName == "" {
		return nil, fmt.Errorf("agent_name is required")
	}
	if task == "" {
		return nil, fmt.Errorf("task is required")
	}
	if agentName == "orchestrator" {
		return nil, fmt.Errorf("cannot call orchestrator recursively")
	}

	// Validate against the live agent list from ARCHITECTURE.md.
	knownAgents := b.loadAgentList()
	if len(knownAgents) > 0 {
		found := false
		var names []string
		for _, e := range knownAgents {
			names = append(names, e.Name)
			if e.Name == agentName {
				found = true
			}
		}
		if !found {
			return nil, fmt.Errorf("unknown agent %q. Available: %s", agentName, strings.Join(names, ", "))
		}
	}

	// Locate the agent definition — prefer .claude/agents/ (Claude-synced), fall back to .agent/agents/**/.
	agentFile := ""
	claudeAgentPath := filepath.Join(b.workspaceRoot, ".claude", "agents", agentName+".md")
	if _, err := os.Stat(claudeAgentPath); err == nil {
		agentFile = claudeAgentPath
	} else {
		_ = filepath.Walk(filepath.Join(b.workspaceRoot, ".agent", "agents"), func(path string, info os.FileInfo, err error) error {
			if err != nil || info.IsDir() {
				return nil
			}
			if strings.EqualFold(filepath.Base(path), agentName+".md") {
				agentFile = path
				return filepath.SkipAll
			}
			return nil
		})
	}
	if agentFile == "" {
		return nil, fmt.Errorf("agent %q not found in .claude/agents/ or .agent/agents/", agentName)
	}

	raw, err := os.ReadFile(agentFile)
	if err != nil {
		return nil, fmt.Errorf("cannot read agent file: %v", err)
	}

	body := string(raw)
	if idx := strings.Index(body, "-->"); idx >= 0 {
		body = strings.TrimSpace(body[idx+3:])
	}
	if strings.HasPrefix(body, "---") {
		end := strings.Index(body[3:], "---")
		if end >= 0 {
			body = strings.TrimSpace(body[3+end+3:])
		}
	}
	systemPrompt := body

	if tierOverride == "" {
		if rules, rErr := b.loadRules(); rErr == nil && rules.AgentTiers != nil {
			if t, ok := rules.AgentTiers[agentName]; ok {
				tierOverride = t
			}
		}
	}

	fmt.Fprintf(os.Stderr, "[INFO] invokeAgent: agent=%s tier=%s file=%s\n", agentName, tierOverride, agentFile)

	// GUARANTEE C — sub-agents run LOCAL ONLY. withLocalOnly disables every cloud
	// fallback path in executePromptLogic so delegated work can never escape to cloud.
	result, err := b.executePromptLogic(withLocalOnly(ctx), task, systemPrompt, task, "", tierOverride, false)
	if err != nil {
		return nil, err
	}
	return result, nil
}

// handleCallAgent is the MCP tool wrapper for invokeAgent.
func (b *BrokerServer) handleCallAgent(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	agentName, _ := req.RequireString("agent_name")
	task := b.getStringArg(req.Params.Arguments, "task")
	tierOverride := b.getStringArg(req.Params.Arguments, "tier")

	if task == "" {
		return mcp.NewToolResultError("task is required"), nil
	}

	result, err := b.invokeAgent(ctx, agentName, task, tierOverride)
	if err != nil {
		return mcp.NewToolResultError(fmt.Sprintf("call_agent failed: %v", err)), nil
	}

	// The agent persona may still self-report an Identity Header (03_gateway.md
	// instructs it to, and some fine-tuned local models do it even when that rule
	// wasn't injected). That self-report is unverified — it has no access to
	// result.Model/result.Source — so it is stripped rather than trusted, and the
	// broker-verified values below are what callers should read instead.
	cleanResponse, hadSelfReport := stripSelfReportedIdentityHeader(result.Response)
	if hadSelfReport {
		fmt.Fprintf(os.Stderr, "[WARN] handleCallAgent: agent %q self-reported an Identity Header; stripped it — verified model is %s/%s\n",
			agentName, result.Source, result.Model)
	}

	isCloud := false
	if rules, rErr := b.loadRules(); rErr == nil {
		isCloud = result.Source == rules.HybridRouting.CloudFallbackProvider
	}

	out := map[string]any{
		"agent":      agentName,
		"response":   cleanResponse,
		"model_used": result.Model,
		"provider":   result.Source,
		"is_cloud":   isCloud,
	}
	jsonData, _ := json.MarshalIndent(out, "", "  ")
	return mcp.NewToolResultText(string(jsonData)), nil
}

// stripSelfReportedIdentityHeader removes the two-line "Identity Header" banner
// (03_gateway.md's IDENTITY HEADER PROTOCOL: a "🤖 Flow: ..." line optionally
// followed by a "🧠 Team Consensus: ..." line) that an agent persona may have
// self-reported. That banner is never trustworthy here — it is unverified prose
// generated by the model itself, not data read from the broker's own routing
// decision — so callers must rely on the model_used/provider fields that
// handleCallAgent stamps from ExecutionResult instead. Returns the cleaned text
// and whether a header was actually found and removed.
func stripSelfReportedIdentityHeader(response string) (string, bool) {
	lines := strings.Split(response, "\n")
	out := make([]string, 0, len(lines))
	removed := false

	for i := 0; i < len(lines); i++ {
		trimmed := strings.TrimSpace(lines[i])
		if strings.HasPrefix(trimmed, "🤖 Flow:") {
			removed = true
			// The Team Consensus line, if present, is part of the same header block.
			if i+1 < len(lines) && strings.HasPrefix(strings.TrimSpace(lines[i+1]), "🧠 Team Consensus:") {
				i++
			}
			continue
		}
		out = append(out, lines[i])
	}

	if !removed {
		return response, false
	}
	// Drop leading blank lines left behind by the removed header.
	cleaned := strings.Join(out, "\n")
	return strings.TrimLeft(cleaned, "\n"), true
}

// handleProvisionLlamaCpp is the MCP tool wrapper for ensureLlamaCppRunning.
func (b *BrokerServer) handleProvisionLlamaCpp(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	tier := b.getStringArg(req.Params.Arguments, "tier")
	if tier == "" {
		tier = "L3"
	}

	url, err := b.ensureLlamaCppRunning(ctx, tier)
	if err != nil {
		return mcp.NewToolResultError(fmt.Sprintf("provision_llamacpp failed: %v", err)), nil
	}

	out := map[string]string{"status": "running", "url": url, "tier": tier}
	jsonData, _ := json.MarshalIndent(out, "", "  ")
	return mcp.NewToolResultText(string(jsonData)), nil
}

func (b *BrokerServer) getBackendHealth(provider string) BackendHealth {
	b.healthCacheMu.RLock()
	defer b.healthCacheMu.RUnlock()
	
	if b.healthCache == nil {
		return BackendHealth{Available: true}
	}
	h, ok := b.healthCache[provider]
	if !ok {
		// Default to available if we haven't checked (especially in CLI mode)
		return BackendHealth{Available: true}
	}
	return h
}
