package main

import (
	"archive/tar"
	"compress/gzip"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"strconv"
	"strings"
	"time"
)

// llamaCppMinVRAMHeadroomMB is a rough safety margin checked before launching a
// new llama-server instance — not a precise per-model budget, just enough to
// refuse launch when the GPU is clearly already full (e.g. Jan holding a large
// model), rather than crashing with an OOM error after the fact.
const llamaCppMinVRAMHeadroomMB = 2048

// ---------- Environment-aware build guidance ----------

// BuildAdvice tells the caller which llama.cpp GGML backend to build with and
// what prerequisite install instructions apply for the detected environment.
// Pure function of EnvironmentInfo — no exec.Command/network calls — so it is
// fully unit-testable without touching the real system.
type BuildAdvice struct {
	CMakeFlag     string
	PrereqMessage string
	Supported     bool
}

// llamaCppBuildAdvice picks GPU-backend flags and prerequisite instructions
// based on the detected environment. WSL and native Linux both build with CUDA,
// but need OPPOSITE driver-install advice (WSL must NOT install a Linux GPU
// driver — one is already passed through from Windows; native Linux needs the
// driver installed normally) — treating them as the same case was the original
// mistake this function exists to avoid.
func llamaCppBuildAdvice(env EnvironmentInfo) BuildAdvice {
	var advice BuildAdvice

	switch {
	case env.IsWSL:
		advice = BuildAdvice{
			Supported: true,
			CMakeFlag: "-DGGML_CUDA=ON",
			PrereqMessage: "WSL detected: install cmake (`sudo apt install cmake`) and the CUDA " +
				"Toolkit via the WSL-Ubuntu specific installer — NOT the regular Ubuntu repo: " +
				"https://developer.nvidia.com/cuda-downloads?target_os=Linux&target_arch=x86_64&Distribution=WSL-Ubuntu " +
				"Install only the `cuda-toolkit-12-x` package. NEVER install `cuda`, `cuda-12-x` " +
				"(without the `-toolkit` suffix), or `cuda-drivers` under WSL2 — those pull in a " +
				"Linux GPU driver that conflicts with the one WSL2 already passes through from " +
				"the Windows host.",
		}
	case env.OS == "linux":
		advice = BuildAdvice{
			Supported: true,
			CMakeFlag: "-DGGML_CUDA=ON",
			PrereqMessage: "Native Linux detected: install cmake and the CUDA Toolkit per the " +
				"standard install guide — here the driver and toolkit install together as usual " +
				"(unlike WSL): https://docs.nvidia.com/cuda/cuda-installation-guide-linux/",
		}
	case env.OS == "darwin":
		advice = BuildAdvice{
			Supported: true,
			CMakeFlag: "-DGGML_METAL=ON",
			PrereqMessage: "macOS detected: no NVIDIA/CUDA toolkit applies here — llama.cpp uses " +
				"Metal for GPU acceleration on Apple Silicon. Install Xcode command line tools: " +
				"`xcode-select --install`.",
		}
	case env.OS == "windows":
		advice = BuildAdvice{
			Supported: false,
			PrereqMessage: "Native Windows detected: building from source is unnecessary here — " +
				"download the official prebuilt win-cuda-x64.zip release directly instead: " +
				"https://github.com/ggml-org/llama.cpp/releases",
		}
	default:
		advice = BuildAdvice{
			Supported:     false,
			PrereqMessage: fmt.Sprintf("Unrecognized OS %q — no build guidance available for this environment.", env.OS),
		}
	}

	if env.IsContainer {
		advice.PrereqMessage += " Also detected: running inside a container — GPU passthrough " +
			"here requires the NVIDIA Container Toolkit (`--gpus all` / nvidia-docker), a " +
			"separate host-level setup from the WSL/native-Linux cases above."
	}

	return advice
}

// ---------- Pure path/JSON helpers (unit-testable without touching the system) ----------

// windowsUserProfileToWSLPath converts a Windows path such as `C:\Users\artur`
// (as printed by `cmd.exe /c echo %USERPROFILE%` via WSL interop) into its
// WSL-mounted equivalent, e.g. `/mnt/c/Users/artur`.
func windowsUserProfileToWSLPath(winPath string) (string, error) {
	winPath = strings.TrimSpace(winPath)
	if len(winPath) < 3 || winPath[1] != ':' {
		return "", fmt.Errorf("not a recognizable Windows path: %q", winPath)
	}
	drive := strings.ToLower(string(winPath[0]))
	rest := strings.ReplaceAll(winPath[2:], "\\", "/")
	return "/mnt/" + drive + rest, nil
}

// jsonTopLevelStringFieldPattern matches a top-level `"key": "value"` pair in a
// JSON document, capturing the `"key":` prefix (with any surrounding
// whitespace) so it can be preserved verbatim when replacing just the value.
func jsonTopLevelStringFieldPattern(key string) *regexp.Regexp {
	return regexp.MustCompile(`"` + regexp.QuoteMeta(key) + `"\s*:\s*"(?:[^"\\]|\\.)*"`)
}

// patchJSONField replaces the value of a top-level string field in raw JSON
// text, preserving every other byte — key order, comments-as-JSON-fields,
// formatting — untouched. Deliberately NOT implemented as an
// unmarshal-into-map-then-marshal round trip: Go's encoding/json sorts map keys
// alphabetically on marshal, which would silently reorder every top-level key
// in router_rules.json on every write, turning it into an unreviewable diff.
func patchJSONField(raw []byte, key, value string) ([]byte, error) {
	encodedValue, err := json.Marshal(value)
	if err != nil {
		return nil, fmt.Errorf("failed to encode value for key %q: %w", key, err)
	}

	pattern := jsonTopLevelStringFieldPattern(key)
	if !pattern.Match(raw) {
		return nil, fmt.Errorf("key %q not found as a top-level string field in JSON", key)
	}

	keyPrefixPattern := regexp.MustCompile(`"` + regexp.QuoteMeta(key) + `"\s*:\s*`)
	patched := pattern.ReplaceAllFunc(raw, func(match []byte) []byte {
		prefix := keyPrefixPattern.Find(match)
		out := make([]byte, 0, len(prefix)+len(encodedValue))
		out = append(out, prefix...)
		out = append(out, encodedValue...)
		return out
	})
	return patched, nil
}

// pickFreePort asks the OS for a free TCP port and immediately releases it.
// Standard Go idiom for "reserve a port to hand to a subprocess" — a small
// TOCTOU window exists until llama-server actually binds it, which is accepted
// practice for this kind of handoff.
func pickFreePort() (int, error) {
	l, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return 0, fmt.Errorf("failed to allocate a free port: %w", err)
	}
	defer l.Close()
	addr, ok := l.Addr().(*net.TCPAddr)
	if !ok {
		return 0, fmt.Errorf("unexpected listener address type %T", l.Addr())
	}
	return addr.Port, nil
}

// ---------- VRAM headroom gate ----------

// checkVRAMHeadroomMB returns free GPU memory in MiB via nvidia-smi. Returns an
// error (never a fabricated number) if nvidia-smi is unavailable or its output
// can't be parsed — callers should treat that as "unknown", not "zero free",
// and proceed without the gate rather than block launch on an unperformable check.
func checkVRAMHeadroomMB(ctx context.Context) (int, error) {
	out, err := exec.CommandContext(ctx, "nvidia-smi",
		"--query-gpu=memory.free", "--format=csv,noheader,nounits").Output()
	if err != nil {
		return 0, fmt.Errorf("nvidia-smi unavailable: %w", err)
	}
	line := strings.TrimSpace(strings.SplitN(string(out), "\n", 2)[0])
	mb, err := strconv.Atoi(line)
	if err != nil {
		return 0, fmt.Errorf("could not parse nvidia-smi output %q: %w", line, err)
	}
	return mb, nil
}

// ---------- Source download + build ----------

// downloadAndExtractTarGz fetches a .tar.gz archive and extracts it under
// destDir, guarding against path-traversal ("zip-slip") entries in the archive.
func downloadAndExtractTarGz(ctx context.Context, url, destDir string) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return err
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("unexpected status %d fetching %s", resp.StatusCode, url)
	}

	gz, err := gzip.NewReader(resp.Body)
	if err != nil {
		return fmt.Errorf("failed to open gzip stream: %w", err)
	}
	defer gz.Close()

	cleanDest := filepath.Clean(destDir)
	tr := tar.NewReader(gz)
	for {
		hdr, err := tr.Next()
		if err == io.EOF {
			return nil
		}
		if err != nil {
			return fmt.Errorf("failed to read tar entry: %w", err)
		}

		target := filepath.Join(destDir, hdr.Name)
		if target != cleanDest && !strings.HasPrefix(target, cleanDest+string(os.PathSeparator)) {
			return fmt.Errorf("tar entry escapes destination dir: %s", hdr.Name)
		}

		switch hdr.Typeflag {
		case tar.TypeDir:
			if err := os.MkdirAll(target, 0755); err != nil {
				return err
			}
		case tar.TypeReg:
			if err := os.MkdirAll(filepath.Dir(target), 0755); err != nil {
				return err
			}
			f, err := os.OpenFile(target, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, os.FileMode(hdr.Mode))
			if err != nil {
				return err
			}
			if _, err := io.Copy(f, tr); err != nil {
				f.Close()
				return err
			}
			f.Close()
		}
	}
}

func (b *BrokerServer) setProvisionStatus(key, status string) {
	b.pullingStatesMu.Lock()
	if b.pullingStates == nil {
		b.pullingStates = make(map[string]string)
	}
	b.pullingStates[key] = status
	b.pullingStatesMu.Unlock()
}

// buildLlamaServerIfNeeded builds llama-server from source at RouterRules.LlamaCppSourceRef
// (or llamaCppDefaultSourceRef if unset), skipping the build entirely if a
// matching version was already built. Status is tracked in b.pullingStates under
// the "llamacpp-build" key — visible via the existing detect_backends Downloads
// field, no new API surface needed.
func (b *BrokerServer) buildLlamaServerIfNeeded(ctx context.Context, rules *RouterRules) (string, error) {
	ref := rules.LlamaCppSourceRef
	if ref == "" {
		ref = llamaCppDefaultSourceRef
	}

	buildRoot := filepath.Join(b.workspaceRoot, ".agent", "mcp-llm-broker", "bin", "llamacpp")
	markerPath := filepath.Join(buildRoot, ".built-ref")
	binPath := filepath.Join(buildRoot, "build", "bin", "llama-server")

	if builtRef, err := os.ReadFile(markerPath); err == nil && strings.TrimSpace(string(builtRef)) == ref {
		if _, statErr := os.Stat(binPath); statErr == nil {
			return binPath, nil
		}
	}

	env := b.detectEnv()
	advice := llamaCppBuildAdvice(env)
	if !advice.Supported {
		return "", fmt.Errorf("building llama-server from source is not supported on this environment: %s", advice.PrereqMessage)
	}
	if _, err := exec.LookPath("cmake"); err != nil {
		return "", fmt.Errorf("cmake not found. %s", advice.PrereqMessage)
	}
	if strings.Contains(advice.CMakeFlag, "CUDA") {
		if _, err := exec.LookPath("nvcc"); err != nil {
			return "", fmt.Errorf("nvcc not found. %s", advice.PrereqMessage)
		}
	}

	b.setProvisionStatus("llamacpp-build", "building")

	srcDir := filepath.Join(buildRoot, "src")
	if err := os.RemoveAll(srcDir); err != nil {
		b.setProvisionStatus("llamacpp-build", "failed")
		return "", fmt.Errorf("failed to clear previous source dir: %w", err)
	}
	if err := os.MkdirAll(srcDir, 0755); err != nil {
		b.setProvisionStatus("llamacpp-build", "failed")
		return "", fmt.Errorf("failed to create source dir: %w", err)
	}

	sourceURL := fmt.Sprintf("https://github.com/ggml-org/llama.cpp/archive/refs/tags/%s.tar.gz", ref)
	if err := downloadAndExtractTarGz(ctx, sourceURL, srcDir); err != nil {
		b.setProvisionStatus("llamacpp-build", "failed")
		return "", fmt.Errorf("failed to download/extract llama.cpp source %s: %w", ref, err)
	}

	// GitHub source tarballs extract into a single top-level "llama.cpp-<ref>" dir.
	entries, err := os.ReadDir(srcDir)
	if err != nil || len(entries) != 1 {
		b.setProvisionStatus("llamacpp-build", "failed")
		return "", fmt.Errorf("unexpected source archive layout in %s", srcDir)
	}
	repoDir := filepath.Join(srcDir, entries[0].Name())
	buildDir := filepath.Join(buildRoot, "build")

	fmt.Fprintf(os.Stderr, "[INFO] llamacpp provisioner: configuring build (%s)\n", advice.CMakeFlag)
	cmakeConfig := exec.CommandContext(ctx, "cmake", "-S", repoDir, "-B", buildDir,
		advice.CMakeFlag, "-DCMAKE_BUILD_TYPE=Release")
	cmakeConfig.Stdout = os.Stderr
	cmakeConfig.Stderr = os.Stderr
	if err := cmakeConfig.Run(); err != nil {
		b.setProvisionStatus("llamacpp-build", "failed")
		return "", fmt.Errorf("cmake configure failed: %w", err)
	}

	fmt.Fprintf(os.Stderr, "[INFO] llamacpp provisioner: building (this takes a few minutes)\n")
	cmakeBuild := exec.CommandContext(ctx, "cmake", "--build", buildDir, "--config", "Release",
		"-j", strconv.Itoa(runtime.NumCPU()))
	cmakeBuild.Stdout = os.Stderr
	cmakeBuild.Stderr = os.Stderr
	if err := cmakeBuild.Run(); err != nil {
		b.setProvisionStatus("llamacpp-build", "failed")
		return "", fmt.Errorf("cmake build failed: %w", err)
	}

	if _, err := os.Stat(binPath); err != nil {
		b.setProvisionStatus("llamacpp-build", "failed")
		return "", fmt.Errorf("build succeeded but llama-server binary not found at %s: %w", binPath, err)
	}

	if err := os.WriteFile(markerPath, []byte(ref), 0644); err != nil {
		fmt.Fprintf(os.Stderr, "[WARN] llamacpp provisioner: build succeeded but failed to write version marker: %v\n", err)
	}

	b.setProvisionStatus("llamacpp-build", "completed")
	return binPath, nil
}

// ---------- Model discovery ----------

// discoverJanGGUF locates the .gguf file Jan already downloaded for modelName,
// via WSL interop with the Windows host (reading %USERPROFILE%) — avoids a
// second multi-GB download of a model already present on disk for Jan.
func (b *BrokerServer) discoverJanGGUF(ctx context.Context, env EnvironmentInfo, modelName string) (string, error) {
	if !env.IsWSL {
		return "", fmt.Errorf("Jan GGUF auto-discovery is only implemented for WSL — configure llamacpp_base_url and a model path manually on this environment")
	}

	cmdCtx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()
	out, err := exec.CommandContext(cmdCtx, "/mnt/c/Windows/System32/cmd.exe", "/c", "echo %USERPROFILE%").Output()
	if err != nil {
		return "", fmt.Errorf("failed to resolve Windows user profile via WSL interop: %w", err)
	}
	wslHome, err := windowsUserProfileToWSLPath(string(out))
	if err != nil {
		return "", fmt.Errorf("could not parse Windows user profile path %q: %w", strings.TrimSpace(string(out)), err)
	}

	ggufPath := filepath.Join(wslHome, "AppData", "Roaming", "Jan", "data", "llamacpp", "models", modelName, "model.gguf")
	if _, err := os.Stat(ggufPath); err != nil {
		return "", fmt.Errorf("model %q not found at %s — has Jan downloaded it yet? %w", modelName, ggufPath, err)
	}
	return ggufPath, nil
}

// ---------- Launch + supervision ----------

func (b *BrokerServer) launchLlamaServer(ctx context.Context, binPath, ggufPath string, port int) error {
	if headroom, err := checkVRAMHeadroomMB(ctx); err == nil && headroom < llamaCppMinVRAMHeadroomMB {
		return fmt.Errorf("insufficient VRAM headroom (%d MiB free, need at least %d MiB) — refusing to launch llama-server to avoid an OOM crash", headroom, llamaCppMinVRAMHeadroomMB)
	}
	// If nvidia-smi itself is unavailable, proceed without the gate — a check
	// that can't be performed must not block launch.

	b.llamaCppCmdMu.Lock()
	if b.llamaCppCmd != nil && b.llamaCppCmd.ProcessState == nil {
		pid := b.llamaCppCmd.Process.Pid
		b.llamaCppCmdMu.Unlock()
		return fmt.Errorf("a llama-server instance managed by this broker is already running (pid %d)", pid)
	}
	b.llamaCppCmdMu.Unlock()

	logPath := filepath.Join(b.workspaceRoot, ".agent", "bus", "llamacpp.log")
	if err := os.MkdirAll(filepath.Dir(logPath), 0755); err != nil {
		return fmt.Errorf("failed to prepare log dir: %w", err)
	}
	logFile, err := os.OpenFile(logPath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
	if err != nil {
		return fmt.Errorf("failed to open log file: %w", err)
	}

	cmd := exec.Command(binPath, "--model", ggufPath, "--port", strconv.Itoa(port), "--host", "127.0.0.1")
	cmd.Stdout = logFile
	cmd.Stderr = logFile
	if err := cmd.Start(); err != nil {
		logFile.Close()
		return fmt.Errorf("failed to start llama-server: %w", err)
	}

	b.llamaCppCmdMu.Lock()
	b.llamaCppCmd = cmd
	b.llamaCppCmdMu.Unlock()
	b.setProvisionStatus("llamacpp-process", "running")

	go func() {
		defer logFile.Close()
		waitErr := cmd.Wait()
		b.setProvisionStatus("llamacpp-process", "stopped")
		if waitErr != nil {
			fmt.Fprintf(os.Stderr, "[WARN] llamacpp provisioner: llama-server exited: %v (see %s)\n", waitErr, logPath)
		}
	}()

	return nil
}

// waitForLlamaCppReady polls the freshly-launched instance until it answers
// /v1/models (or the deadline expires), trying the WSL gateway address too if
// localhost isn't reachable from this side — same dual-check pattern already
// used for Jan/LM Studio elsewhere in this file.
func (b *BrokerServer) waitForLlamaCppReady(ctx context.Context, localURL string, env EnvironmentInfo) (string, error) {
	deadline := time.Now().Add(30 * time.Second)
	logPath := filepath.Join(b.workspaceRoot, ".agent", "bus", "llamacpp.log")

	for time.Now().Before(deadline) {
		probeCtx, cancel := context.WithTimeout(ctx, 1*time.Second)
		_, err := b.fetchOpenAICompatibleModels(probeCtx, localURL)
		cancel()
		if err == nil {
			return localURL, nil
		}

		if env.IsWSL && env.WSLGateway != "" {
			gatewayURL := strings.Replace(localURL, "127.0.0.1", env.WSLGateway, 1)
			gwCtx, gwCancel := context.WithTimeout(ctx, 1*time.Second)
			_, gwErr := b.fetchOpenAICompatibleModels(gwCtx, gatewayURL)
			gwCancel()
			if gwErr == nil {
				return gatewayURL, nil
			}
		}

		time.Sleep(500 * time.Millisecond)
	}
	return "", fmt.Errorf("llama-server did not become reachable within 30s (check %s)", logPath)
}

// ---------- Top-level entry point ----------

// ensureLlamaCppRunning builds (if needed), launches, and self-configures a
// standalone llama-server instance for the given tier. Idempotent: if the
// broker already has one tracked as running, launchLlamaServer refuses to
// start a second one rather than silently doing nothing — callers (the
// provision_llamacpp tool, and the health-check auto-relaunch path) both go
// through this single entry point.
func (b *BrokerServer) ensureLlamaCppRunning(ctx context.Context, tier string) (string, error) {
	rules, err := b.loadRules()
	if err != nil {
		return "", fmt.Errorf("failed to load rules: %w", err)
	}

	binPath, err := b.buildLlamaServerIfNeeded(ctx, rules)
	if err != nil {
		return "", err
	}

	env := b.detectEnv()
	modelName := b.getStringOrFirst(rules.Models[ProviderLlamaCpp][tier])
	if modelName == "" {
		return "", fmt.Errorf("no llamacpp model configured for tier %s in router_rules.json", tier)
	}

	ggufPath, err := b.discoverJanGGUF(ctx, env, modelName)
	if err != nil {
		return "", err
	}

	port, err := pickFreePort()
	if err != nil {
		return "", err
	}

	if err := b.launchLlamaServer(ctx, binPath, ggufPath, port); err != nil {
		return "", err
	}

	localURL := fmt.Sprintf("http://127.0.0.1:%d", port)
	resolvedURL, err := b.waitForLlamaCppReady(ctx, localURL, env)
	if err != nil {
		return "", err
	}

	if err := b.patchRouterRulesLlamaCppURL(resolvedURL); err != nil {
		fmt.Fprintf(os.Stderr, "[WARN] llamacpp provisioner: launched but failed to self-write router_rules.json: %v\n", err)
	}

	return resolvedURL, nil
}

// patchRouterRulesLlamaCppURL writes the resolved llama-server URL back into
// router_rules.json's llamacpp_base_url field so subsequent broker calls (and
// process restarts) pick it up without any manual step.
func (b *BrokerServer) patchRouterRulesLlamaCppURL(url string) error {
	path := filepath.Join(b.workspaceRoot, ".agent", "config", "router_rules.json")
	raw, err := os.ReadFile(path)
	if err != nil {
		return fmt.Errorf("failed to read router_rules.json: %w", err)
	}

	patched, err := patchJSONField(raw, "llamacpp_base_url", url)
	if err != nil {
		return fmt.Errorf("failed to patch llamacpp_base_url: %w", err)
	}

	if err := os.WriteFile(path, patched, 0644); err != nil {
		return fmt.Errorf("failed to write router_rules.json: %w", err)
	}

	fmt.Fprintf(os.Stderr, "[INFO] llamacpp provisioner: wrote llamacpp_base_url=%s to router_rules.json\n", url)
	return nil
}

// maybeAutoRelaunchLlamaCpp is called from the health-check loop. It only acts
// when a build already exists (never triggers the first, heavy source build
// automatically — that requires an explicit provision_llamacpp call) and rate-
// limits relaunch attempts so a persistently broken setup doesn't get hammered
// every health-check tick.
func (b *BrokerServer) maybeAutoRelaunchLlamaCpp(ctx context.Context) {
	markerPath := filepath.Join(b.workspaceRoot, ".agent", "mcp-llm-broker", "bin", "llamacpp", ".built-ref")
	if _, err := os.Stat(markerPath); err != nil {
		return // never built yet — wait for an explicit provision_llamacpp call
	}

	b.llamaCppCmdMu.Lock()
	if b.llamaCppCmd != nil && b.llamaCppCmd.ProcessState == nil {
		b.llamaCppCmdMu.Unlock()
		return // already tracked as running — treat the health failure as transient
	}
	if time.Since(b.llamaCppLastRelaunchAttempt) < 60*time.Second {
		b.llamaCppCmdMu.Unlock()
		return
	}
	b.llamaCppLastRelaunchAttempt = time.Now()
	b.llamaCppCmdMu.Unlock()

	go func() {
		relaunchCtx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
		defer cancel()
		if _, err := b.ensureLlamaCppRunning(relaunchCtx, "L3"); err != nil {
			fmt.Fprintf(os.Stderr, "[WARN] llamacpp provisioner: auto-relaunch failed: %v\n", err)
		}
	}()
}
