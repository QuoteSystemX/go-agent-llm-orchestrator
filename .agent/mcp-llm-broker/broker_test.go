package main

import (
	"context"
	"encoding/json"
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
	srv := &BrokerServer{
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
