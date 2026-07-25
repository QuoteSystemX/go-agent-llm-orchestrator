package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/mark3labs/mcp-go/mcp"
)

// -------- EMA Latency Balancing Tests --------

func TestEMALatencyUpdate(t *testing.T) {
	srv := &BrokerServer{
		healthCache: make(map[string]BackendHealth),
	}

	// First call: TotalTokens (0) < EMAMinTokensForReliability (100) → cold start → simple avg
	// msPerToken = 1000ms / 100tokens = 10.0
	srv.updateEMALatency("ollama", 1000*time.Millisecond, 100)
	h := srv.getBackendHealth("ollama")
	if h.EMAMsPerToken != 10.0 {
		t.Errorf("Expected 10.0 ms/token (simple avg), got %f", h.EMAMsPerToken)
	}
	if h.TotalTokens != 100 {
		t.Errorf("Expected 100 total tokens, got %d", h.TotalTokens)
	}

	// Second call: TotalTokens (100) is NOT < EMAMinTokensForReliability (100) — EMA kicks in
	// msPerToken = 2000ms / 100tokens = 20.0
	// ema = 0.3*20.0 + 0.7*10.0 = 6.0 + 7.0 = 13.0
	srv.updateEMALatency("ollama", 2000*time.Millisecond, 100)
	h = srv.getBackendHealth("ollama")
	expectedEMA := EMAAlpha*20.0 + (1-EMAAlpha)*10.0
	if math.Abs(h.EMAMsPerToken-expectedEMA) > 0.01 {
		t.Errorf("Expected ~%f ms/token (EMA), got %f", expectedEMA, h.EMAMsPerToken)
	}

	// Third call: EMA again
	// msPerToken = 3000ms / 100tokens = 30.0
	// ema = 0.3*30.0 + 0.7*13.0 = 9.0 + 9.1 = 18.1
	srv.updateEMALatency("ollama", 3000*time.Millisecond, 100)
	h = srv.getBackendHealth("ollama")
	expectedEMA2 := EMAAlpha*30.0 + (1-EMAAlpha)*13.0
	if math.Abs(h.EMAMsPerToken-expectedEMA2) > 0.01 {
		t.Errorf("Expected ~%f ms/token (EMA), got %f", expectedEMA2, h.EMAMsPerToken)
	}
}

func TestPickBestLocalWithEMA(t *testing.T) {
	srv := &BrokerServer{
		healthCache: map[string]BackendHealth{
			"ollama": {Available: true, EMAMsPerToken: 50.0, TotalTokens: 200},
		},
	}

	// getLocalCandidates only searches within ProviderOllama config
	// So we model different providers as different models on ollama
	rules := &RouterRules{
		Models: map[string]ModelTiers{
			"ollama": {
				"L2":     "model-a",
				"L2_alt": []interface{}{"model-b", "model-c", "model-d"},
			},
		},
		ModelRankings: map[string]json.RawMessage{
			"model-a": []byte(`{"rank_score": 90}`), // highest rank
			"model-b": []byte(`{"rank_score": 60}`),
			"model-c": []byte(`{"rank_score": 70}`),
			"model-d": []byte(`{"rank_score": 80}`),
		},
	}

	// pulled from different providers
	pulledModels := map[string]string{
		"model-a": "jan",       // EMA=unknown (no health data) → hasEMA=false
		"model-b": "ollama",    // EMA=50ms/tok
		"model-c": "lm-studio", // EMA=unknown → hasEMA=false
		"model-d": "ollama",    // EMA=50ms/tok
	}

	// Candidates should be: model-d, model-b, model-c, model-a (sorted by rank then by EMA)
	// model-a: jan provider, no health data → hasEMA=false
	// model-b: ollama, EMA=50 → hasEMA=true
	// model-c: lm-studio, no health data → hasEMA=false
	// model-d: ollama, EMA=50 → hasEMA=true
	// After sorting: those with EMA come first, sorted by EMA asc (both 50), then rank desc
	// So: model-d (rank 80) → model-b (rank 60) → then model-c (rank 70) → model-a (rank 90)
	model, provider, ok := srv.pickBestLocal("L2", rules, pulledModels)
	if !ok {
		t.Fatal("Expected true, got false")
	}
	// model-d has EMA data (hasEMA=true) and lowest EMA among those with data (actually same as model-b)
	// Both have EMA=50, so tiebreaker is rank score: model-d (80) > model-b (60)
	if model != "model-d" {
		t.Errorf("Expected model-d (has EMA, higher rank), got %s/%s", provider, model)
	}
}

func TestPickBestLocalExcludesHighLatency(t *testing.T) {
	tmpDir := t.TempDir()
	srv := &BrokerServer{
		workspaceRoot: tmpDir,
		healthCache: map[string]BackendHealth{
			"ollama": {Available: true, EMAMsPerToken: 50000.0, TotalTokens: 200}, // exceeds threshold
		},
	}

	rules := &RouterRules{
		Models: map[string]ModelTiers{
			"ollama": {
				"L2":     "model-a", // on ollama, 50000ms/tok → excluded
				"L2_alt": []interface{}{"model-b"},
			},
		},
		ModelRankings: map[string]json.RawMessage{
			"model-a": []byte(`{"rank_score": 90}`),
			"model-b": []byte(`{"rank_score": 80}`),
		},
		CircuitBreaker: &CircuitBreakerConfig{
			SoftEMAThreshold: 60000.0,
		},
	}

	// Write rules to temporary file so b.loadRules() can read it inside isCircuitOpen
	rulesPath := filepath.Join(tmpDir, ".agent", "config", "router_rules.json")
	if err := os.MkdirAll(filepath.Dir(rulesPath), 0755); err != nil {
		t.Fatalf("failed to create config dir: %v", err)
	}
	rulesData, err := json.Marshal(rules)
	if err != nil {
		t.Fatalf("failed to marshal rules: %v", err)
	}
	if err := os.WriteFile(rulesPath, rulesData, 0644); err != nil {
		t.Fatalf("failed to write rules: %v", err)
	}

	pulledModels := map[string]string{
		"model-a": "ollama",  // EMA=50000 → excluded by threshold
		"model-b": "ollama",  // same provider, but different model — both get same EMA
	}

	// Both models are on ollama with EMA=50000 > threshold, so both excluded
	// pickBestLocal falls through to the last-resort fallback: return first scored candidate
	model, provider, ok := srv.pickBestLocal("L2", rules, pulledModels)
	if !ok {
		t.Fatal("Expected true (fallback), got false")
	}
	if model == "" {
		t.Errorf("Expected a fallback model, got empty")
	}
	if provider != "ollama" {
		t.Errorf("Expected ollama, got %s", provider)
	}
}

// -------- JSON Schema Tests --------

func TestIsValidJSON(t *testing.T) {
	if !isValidJSON(`{"name": "test"}`) {
		t.Error("Expected valid JSON")
	}
	if !isValidJSON(`[1, 2, 3]`) {
		t.Error("Expected valid JSON array")
	}
	if isValidJSON(`not json`) {
		t.Error("Expected invalid JSON")
	}
	if isValidJSON(`{broken`) {
		t.Error("Expected invalid JSON")
	}
	if !isValidJSON(`42`) {
		t.Error("Expected valid JSON number")
	}
}

func TestExecuteLLMCallWithJSONSchemaOllama(t *testing.T) {
	// Mock Ollama server that checks for format field
	ollamaServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		var payload map[string]interface{}
		json.Unmarshal(body, &payload)

		_, hasFormat := payload["format"]
		if !hasFormat {
			t.Error("Expected 'format' field in Ollama payload when json_schema provided")
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"response": "{\"name\": \"test\", \"value\": 42}", "eval_count": 10, "eval_duration": 1000000000}`))
	}))
	defer ollamaServer.Close()

	srv := &BrokerServer{
		isCLI:        false,
		healthCache:  make(map[string]BackendHealth),
	}
	srv.workspaceRoot = "../.."

	ctx := context.Background()
	resp, err := srv.executeLLMCall(ctx, "test-model", ProviderOllama, ollamaServer.URL,
		"Generate a JSON object", "", `{"type": "object", "properties": {"name": {"type": "string"}}}`, false, 0.1, 0)
	if err != nil {
		t.Fatalf("executeLLMCall failed: %v", err)
	}
	if resp != `{"name": "test", "value": 42}` {
		t.Errorf("Expected JSON response, got %q", resp)
	}
}

func TestExecuteLLMCallWithJSONSchemaOpenAI(t *testing.T) {
	// Mock OpenAI-compatible server (LM Studio provider) that checks for response_format.
	// Note: Jan uses the Anthropic /messages API which doesn't use response_format.
	openaiServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		var payload map[string]interface{}
		json.Unmarshal(body, &payload)

		rf, hasResponseFormat := payload["response_format"]
		if !hasResponseFormat {
			t.Error("Expected 'response_format' field in OpenAI payload when json_schema provided")
		}
		if rfMap, ok := rf.(map[string]interface{}); ok {
			if rfMap["type"] != "json_schema" {
				t.Errorf("Expected response_format type 'json_schema', got %v", rfMap["type"])
			}
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"choices": [{"message": {"content": "{\"result\": \"ok\"}"}}], "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}`))
	}))
	defer openaiServer.Close()

	srv := &BrokerServer{
		isCLI:       false,
		healthCache: make(map[string]BackendHealth),
	}
	srv.workspaceRoot = "../.."

	ctx := context.Background()
	// Use LM Studio provider — it uses the OpenAI /v1/chat/completions format.
	resp, err := srv.executeLLMCall(ctx, "test-model", ProviderLMStudio, openaiServer.URL,
		"Generate a JSON", "", `{"type": "object", "properties": {"result": {"type": "string"}}}`, false, 0.1, 0)
	if err != nil {
		t.Fatalf("executeLLMCall failed: %v", err)
	}
	if resp != `{"result": "ok"}` {
		t.Errorf("Expected JSON response, got %q", resp)
	}
}

func TestExecutePromptWithInvalidJSONSchema(t *testing.T) {
	srv := &BrokerServer{}
	ctx := context.Background()
	req := mcp.CallToolRequest{
		Params: mcp.CallToolParams{
			Name: "execute_prompt",
			Arguments: map[string]interface{}{
				"prompt":      "test",
				"json_schema": "not valid json",
			},
		},
	}

	res, err := srv.handleExecutePrompt(ctx, req)
	if err != nil {
		t.Fatalf("handleExecutePrompt failed: %v", err)
	}
	if !res.IsError {
		t.Fatal("Expected error for invalid JSON schema, got success")
	}
}

// -------- Telemetry & Budget Tests --------

func TestEstimateTokenCount(t *testing.T) {
	if n := estimateTokenCount("hello world"); n != 2 {
		t.Errorf("Expected ~2 tokens for short text, got %d", n)
	}
	if n := estimateTokenCount(""); n != 0 {
		t.Errorf("Expected 0 for empty, got %d", n)
	}
	// Longer text: ~100 chars = ~25 tokens
	longText := strings.Repeat("hello world ", 10) // 120 chars
	if n := estimateTokenCount(longText); n != 30 {
		t.Errorf("Expected ~30 tokens for 120 chars, got %d", n)
	}
}

func TestIsBudgetExceeded(t *testing.T) {
	tmpDir := t.TempDir()

	// Create telemetry with high cost at expected path
	telemetryPath := filepath.Join(tmpDir, ".agent", "bus", "telemetry.json")
	os.MkdirAll(filepath.Dir(telemetryPath), 0755)
	telemetryData := `{"total_cost_usd": 10.0, "calls": []}`
	os.WriteFile(telemetryPath, []byte(telemetryData), 0644)

	// Create watchdog with limit 2.0 at expected path
	watchdogPath := filepath.Join(tmpDir, ".agent", "config", "watchdog_rules.json")
	os.MkdirAll(filepath.Dir(watchdogPath), 0755)
	watchdogData := `{"limits": {"cost_limit_per_task_usd": 2.0}}`
	os.WriteFile(watchdogPath, []byte(watchdogData), 0644)

	srv := &BrokerServer{
		workspaceRoot: tmpDir,
	}

	rules := &RouterRules{
		Scoring: ScoringConfig{
			Budget: BudgetConfig{
				ThresholdRatio: 0.85,
			},
		},
	}

	// Cost 10.0 > 2.0*0.85 = 1.7, so should be exceeded
	if !srv.isBudgetExceeded(rules) {
		t.Error("Expected budget to be exceeded (10.0 > 1.7)")
	}
}

func TestIsBudgetNotExceeded(t *testing.T) {
	tmpDir := t.TempDir()

	// Create telemetry with low cost at expected path
	telemetryPath := filepath.Join(tmpDir, ".agent", "bus", "telemetry.json")
	os.MkdirAll(filepath.Dir(telemetryPath), 0755)
	telemetryData := `{"total_cost_usd": 0.5, "calls": []}`
	os.WriteFile(telemetryPath, []byte(telemetryData), 0644)

	watchdogPath := filepath.Join(tmpDir, ".agent", "config", "watchdog_rules.json")
	os.MkdirAll(filepath.Dir(watchdogPath), 0755)
	watchdogData := `{"limits": {"cost_limit_per_task_usd": 2.0}}`
	os.WriteFile(watchdogPath, []byte(watchdogData), 0644)

	srv := &BrokerServer{
		workspaceRoot: tmpDir,
	}

	rules := &RouterRules{
		Scoring: ScoringConfig{
			Budget: BudgetConfig{
				ThresholdRatio: 0.85,
			},
		},
	}

	// Cost 0.5 < 2.0*0.85 = 1.7, so should NOT be exceeded
	if srv.isBudgetExceeded(rules) {
		t.Error("Expected budget NOT to be exceeded (0.5 < 1.7)")
	}
}

// Note: Test for updateTelemetryAfterCall needs write permissions.
// We verify it doesn't panic and produces a valid telemetry file.
func TestUpdateTelemetryAfterCall(t *testing.T) {
	tmpDir := t.TempDir()
	srv := &BrokerServer{
		workspaceRoot: tmpDir,
		semaphores:    make(map[string]chan struct{}),
	}

	// Call with free provider (Ollama) - should not write telemetry
	srv.updateTelemetryAfterCall("ollama", "test-model", "hello", "world", 10)
	telemetryPath := filepath.Join(tmpDir, ".agent", "bus", "telemetry.json")
	if _, err := os.Stat(telemetryPath); err == nil {
		t.Error("Telemetry file should NOT exist for free provider")
	}

	// Call with paid provider (antigravity)
	srv.updateTelemetryAfterCall("antigravity", "gemini-3-flash", "test prompt with enough tokens", "response content here", 20)
	data, err := os.ReadFile(telemetryPath)
	if err != nil {
		t.Fatalf("Telemetry file should exist for paid provider: %v", err)
	}

	var telemetry struct {
		TotalCostUSD float64 `json:"total_cost_usd"`
		Calls        []struct {
			Provider string `json:"provider"`
			Model    string `json:"model"`
			CostUSD  float64 `json:"cost_usd"`
		} `json:"calls"`
	}
	if err := json.Unmarshal(data, &telemetry); err != nil {
		t.Fatalf("Failed to parse telemetry: %v", err)
	}
	if telemetry.TotalCostUSD <= 0 {
		t.Errorf("Expected positive cost, got %f", telemetry.TotalCostUSD)
	}
	if len(telemetry.Calls) != 1 {
		t.Errorf("Expected 1 call, got %d", len(telemetry.Calls))
	}
	if telemetry.Calls[0].Provider != "antigravity" {
		t.Errorf("Expected antigravity, got %s", telemetry.Calls[0].Provider)
	}
}

// -------- Self-Reported Identity Header Stripping Tests --------
//
// Local agent personas are instructed (03_gateway.md) to self-report a
// "🤖 Flow: ... 🧠 Model: ..." header, but they have no access to the broker's
// real routing decision. Observed behavior: some models copy the static
// benchmark example verbatim, others fabricate a plausible-but-wrong value.
// handleCallAgent must never trust this text — it strips it and stamps the
// verified model_used/provider fields from ExecutionResult instead.

func TestStripSelfReportedIdentityHeader_FullBanner(t *testing.T) {
	input := "🤖 Flow: **[L4]** | 📈 **TPS**: 129 | 🪙 **Tokens**: 2048/512 | 🧠 **Model**: qwen3-coder:30b | 🔄 **Process**: CoAT → Audit → Verdict\n" +
		"🧠 Team Consensus: **Migration requires deterministic guards** | 👤 Agent: **@red-team** | 📈 Health: **94%** | 🛡️ **Sentinel**: **ACTIVE**\n" +
		"\n" +
		"### 🔴 Red-Team Critique\nActual content here."

	got, removed := stripSelfReportedIdentityHeader(input)
	if !removed {
		t.Fatal("Expected header to be detected and removed")
	}
	if strings.Contains(got, "Flow:") || strings.Contains(got, "Team Consensus") {
		t.Errorf("Header lines leaked into cleaned output: %q", got)
	}
	if !strings.Contains(got, "Actual content here.") {
		t.Errorf("Real content was dropped along with the header: %q", got)
	}
}

func TestStripSelfReportedIdentityHeader_PlaceholderBanner(t *testing.T) {
	// Observed variant: model leaves unknown fields as "-" instead of fabricating values.
	input := "🤖 Flow: **[L3]** | 📈 **TPS**: - | 🪙 **Tokens**: - | 🧠 **Model**: - | 🔄 **Process**: Red-Team Audit\n" +
		"🧠 Team Consensus: **Parser guards required** | 👤 Agent: **@red-team** | 📈 Health: **-** | 🛡️ **Sentinel**: **ACTIVE**\n" +
		"Body text."

	got, removed := stripSelfReportedIdentityHeader(input)
	if !removed {
		t.Fatal("Expected placeholder-style header to be detected and removed")
	}
	if strings.TrimSpace(got) != "Body text." {
		t.Errorf("Expected only body text to remain, got %q", got)
	}
}

func TestStripSelfReportedIdentityHeader_FlowLineWithoutConsensusLine(t *testing.T) {
	// The Team Consensus line is optional in the spec — must not eat unrelated content.
	input := "🤖 Flow: **[L2]**\nSome other line that is not a header.\nBody text."

	got, removed := stripSelfReportedIdentityHeader(input)
	if !removed {
		t.Fatal("Expected Flow line to be detected and removed")
	}
	if !strings.Contains(got, "Some other line that is not a header.") {
		t.Errorf("Unrelated line following Flow was incorrectly stripped: %q", got)
	}
}

func TestStripSelfReportedIdentityHeader_NoHeaderPresent(t *testing.T) {
	input := "Just a plain response with no identity header at all."

	got, removed := stripSelfReportedIdentityHeader(input)
	if removed {
		t.Error("Expected no header to be detected")
	}
	if got != input {
		t.Errorf("Response without a header must be returned unchanged, got %q", got)
	}
}

func TestStripSelfReportedIdentityHeader_LeadingWhitespaceOnFlowLine(t *testing.T) {
	input := "  🤖 Flow: **[L1]** | 🧠 **Model**: gemma-4-12B\nBody."

	got, removed := stripSelfReportedIdentityHeader(input)
	if !removed {
		t.Fatal("Expected indented Flow line to still be detected")
	}
	if !strings.Contains(got, "Body.") {
		t.Errorf("Body content was lost: %q", got)
	}
}

// -------- Standalone llama-server (ProviderLlamaCpp) Tests --------

func TestGetExecutionURL_LlamaCpp_UsesConfiguredURL(t *testing.T) {
	srv := &BrokerServer{}
	ctx := context.Background()
	env := EnvironmentInfo{OS: "linux"}
	rules := &RouterRules{LlamaCppBaseURL: "http://172.31.0.1:54321"}

	got := srv.getExecutionURL(ctx, ProviderLlamaCpp, env, rules)
	if got != "http://172.31.0.1:54321" {
		t.Errorf("Expected configured llamacpp_base_url to be used verbatim, got %q", got)
	}
}

func TestGetExecutionURL_LlamaCpp_FallsBackToDefaultWhenUnconfigured(t *testing.T) {
	srv := &BrokerServer{}
	ctx := context.Background()
	env := EnvironmentInfo{OS: "linux"}
	rules := &RouterRules{} // LlamaCppBaseURL left empty

	got := srv.getExecutionURL(ctx, ProviderLlamaCpp, env, rules)
	if got != DefaultLlamaCppURL {
		t.Errorf("Expected fallback to DefaultLlamaCppURL when unconfigured, got %q", got)
	}
}

// -------- checkAllHealth Merge-Not-Overwrite Tests --------
//
// checkAllHealth runs every 20s and used to replace the whole BackendHealth entry
// with a fresh struct literal, silently wiping CircuitState/ConsecutiveFailures set
// moments earlier by a real completion failure (recordProviderFailure). This meant
// an OPEN circuit for a flaky provider (e.g. Jan returning EOF on /v1/messages while
// still answering /v1/models) would self-heal back to Closed on the very next health
// tick, even though nothing about the real failure was fixed.

func TestMergeHealthCheckResult_PreservesCircuitStateOnFailureProbe(t *testing.T) {
	existing := BackendHealth{
		CircuitState:        CircuitOpen,
		ConsecutiveFailures: 5,
	}

	got := mergeHealthCheckResult(existing, false, 50*time.Millisecond)

	if got.CircuitState != CircuitOpen {
		t.Errorf("Expected CircuitState to remain OPEN after a periodic health probe, got %v", got.CircuitState)
	}
	if got.ConsecutiveFailures != 5 {
		t.Errorf("Expected ConsecutiveFailures to survive the merge, got %d", got.ConsecutiveFailures)
	}
	if got.Available {
		t.Error("Expected Available=false to be recorded from the failed probe")
	}
}

func TestMergeHealthCheckResult_PreservesCircuitStateOnSuccessProbe(t *testing.T) {
	// Even a successful lightweight /v1/models probe must not silently reset a
	// circuit that a real completion failure opened — only recordProviderSuccess
	// (driven by an actual successful completion) is allowed to close it.
	existing := BackendHealth{
		CircuitState:        CircuitOpen,
		ConsecutiveFailures: 3,
	}

	got := mergeHealthCheckResult(existing, true, 10*time.Millisecond)

	if got.CircuitState != CircuitOpen {
		t.Errorf("Expected CircuitState to remain OPEN — only real request success should close it, got %v", got.CircuitState)
	}
	if !got.Available {
		t.Error("Expected Available=true to be recorded from the successful probe")
	}
	if got.Latency != 10*time.Millisecond {
		t.Errorf("Expected Latency to be updated, got %v", got.Latency)
	}
}

// -------- Agent Discovery Tests (live filesystem scan) --------
// Regression coverage for tasks/2026-07-25-mcp-llm-broker-call-agent-drops-management-tier-agents.md:
// loadAgentList used to parse ARCHITECTURE.md's Agents table, silently dropping any
// agent (notably the whole management/ squad-lead/C-level tier) added without a
// matching row. It now scans .agent/agents/**/*.md directly instead — an
// intermediate compiled-manifest design was tried and removed as unnecessary
// (see this task's history) once weighed against the actual trust model: these
// files are committed repo content, and invokeAgent already trusts a single
// such file's full body as the system prompt without any manifest gate.

func TestLoadAgentListScansAgentsDirDirectly(t *testing.T) {
	tmpDir := t.TempDir()
	agentsDir := filepath.Join(tmpDir, ".agent", "agents")

	write := func(rel, name, desc string) {
		p := filepath.Join(agentsDir, rel)
		if err := os.MkdirAll(filepath.Dir(p), 0755); err != nil {
			t.Fatal(err)
		}
		content := fmt.Sprintf("---\nname: %s\ndescription: %s\n---\nBody", name, desc)
		if err := os.WriteFile(p, []byte(content), 0644); err != nil {
			t.Fatal(err)
		}
	}

	// management/ tier, no ARCHITECTURE.md row for either of these — exactly
	// the scenario the original bug made uncallable.
	write("management/cto.md", "cto", "Chief Technology Officer.")
	write("management/backend-lead.md", "backend-lead", "Backend Engineering Lead.")
	write("core/orchestrator.md", "orchestrator", "Must never be delegate-able.")
	write("specialists/go/go-specialist.md", "go-specialist", "Go expert.")

	// A stale/incomplete ARCHITECTURE.md must have zero influence now.
	archPath := filepath.Join(tmpDir, ".agent", "ARCHITECTURE.md")
	os.WriteFile(archPath, []byte("## 🤖 Agents (1)\n\n| `go-specialist` | Go expert |\n"), 0644)

	srv := &BrokerServer{workspaceRoot: tmpDir}
	entries := srv.loadAgentList()

	if len(entries) != 3 {
		t.Fatalf("expected 3 entries (orchestrator excluded from 4), got %d: %+v", len(entries), entries)
	}

	byName := map[string]agentEntry{}
	for _, e := range entries {
		byName[e.Name] = e
	}

	for _, want := range []string{"cto", "backend-lead", "go-specialist"} {
		if _, ok := byName[want]; !ok {
			t.Errorf("expected %q (a real agent file on disk) to be resolvable via loadAgentList, got %+v", want, entries)
		}
	}
	if _, ok := byName["orchestrator"]; ok {
		t.Error("orchestrator must be excluded from loadAgentList — it must never be delegated to")
	}
}

func TestLoadAgentListIgnoresClaudeAgentsDir(t *testing.T) {
	// .claude/agents/ also carries wf-*.md workflow-derived pseudo-agents that
	// were never part of ARCHITECTURE.md's Agents table — loadAgentList's scope
	// must stay .agent/agents/** only, matching that prior scope exactly.
	tmpDir := t.TempDir()
	claudeAgent := filepath.Join(tmpDir, ".claude", "agents", "wf-brainstorm.md")
	os.MkdirAll(filepath.Dir(claudeAgent), 0755)
	os.WriteFile(claudeAgent, []byte("---\nname: brainstorm\ndescription: Structured brainstorming.\n---\nBody"), 0644)

	srv := &BrokerServer{workspaceRoot: tmpDir}
	entries := srv.loadAgentList()

	for _, e := range entries {
		if e.Name == "brainstorm" {
			t.Error("loadAgentList must not scan .claude/agents/ — brainstorm should not appear")
		}
	}
}

func TestLoadAgentListEmptyDirReturnsEmptyNotError(t *testing.T) {
	tmpDir := t.TempDir() // no .agent/agents/ at all
	srv := &BrokerServer{workspaceRoot: tmpDir}

	entries := srv.loadAgentList()
	if len(entries) != 0 {
		t.Errorf("expected no entries when .agent/agents/ is absent, got %+v", entries)
	}
}

func TestParseAgentFrontmatterSurvivesDashesInsideAComment(t *testing.T) {
	// Real bug found while implementing this fix: cto.md has a YAML comment
	// containing "---" inside a nested delegates_to list
	// ("# --- Squad Leads (primary routing layer) ---"). A blind
	// strings.Index(content, "---") would find that comment's dashes instead
	// of the real closing frontmatter delimiter and truncate the block early.
	content := "---\n" +
		"name: cto\n" +
		"description: Chief Technology Officer.\n" +
		"hierarchy:\n" +
		"  delegates_to:\n" +
		"    # --- Squad Leads (primary routing layer) ---\n" +
		"    - backend-lead\n" +
		"---\nBody"

	name, description := parseAgentFrontmatter(content)

	if name != "cto" {
		t.Errorf("expected name %q, got %q", "cto", name)
	}
	if description != "Chief Technology Officer." {
		t.Errorf("expected description %q, got %q", "Chief Technology Officer.", description)
	}
}
