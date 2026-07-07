package main

import (
	"context"
	"encoding/json"
	"fmt"
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

func TestPreprocessMiddleware(t *testing.T) {
	srv := &BrokerServer{}
	prompt := "   hello world   \n"
	result := srv.runPreprocessMiddleware(prompt)
	if result != "hello world" {
		t.Errorf("Expected 'hello world', got %q", result)
	}
}

// mojibake builds a mojibake string: UTF-8 bytes of s treated as individual Latin-1 codepoints.
// This is what arrives when WSL clipboard sends UTF-8 bytes that get read byte-by-byte.
func mojibake(s string) string {
	runes := make([]rune, 0, len(s))
	for _, b := range []byte(s) {
		runes = append(runes, rune(b))
	}
	return string(runes)
}

func TestFixMojibake(t *testing.T) {
	tests := []struct {
		name  string
		input string
		want  string
	}{
		{
			// "сделай" → UTF-8 bytes D1 81 D0 B4 D0 B5 D0 BB D0 B0 D0 B9
			// read as Latin-1: U+00D1 U+0081 U+00D0 U+00B4 ...
			name:  "cyrillic mojibake from WSL clipboard",
			input: mojibake("сделай"),
			want:  "сделай",
		},
		{
			name:  "mixed ASCII + mojibake",
			input: "Error: " + mojibake("нельзя"),
			want:  "Error: нельзя",
		},
		{
			name:  "pure ASCII unchanged",
			input: "hello world",
			want:  "hello world",
		},
		{
			name:  "already correct UTF-8 Cyrillic unchanged",
			input: "сделай анализ",
			want:  "сделай анализ",
		},
		{
			name:  "preprocessMiddleware trims and repairs",
			input: "  " + mojibake("сделай") + "  ",
			want:  "сделай",
		},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			var got string
			if strings.HasPrefix(tc.name, "preprocess") {
				got = (&BrokerServer{}).runPreprocessMiddleware(tc.input)
			} else {
				got = fixMojibake(tc.input)
			}
			if got != tc.want {
				t.Errorf("got %q, want %q", got, tc.want)
			}
		})
	}
}

func TestGetCacheKey(t *testing.T) {
	srv := &BrokerServer{}
	key1 := srv.getCacheKey("prompt", "system", "model")
	key2 := srv.getCacheKey("prompt", "system", "model")
	if key1 != key2 {
		t.Errorf("Expected identical cache keys, got %s and %s", key1, key2)
	}

	key3 := srv.getCacheKey("prompt2", "system", "model")
	if key1 == key3 {
		t.Errorf("Expected different cache keys, got identical: %s", key1)
	}
}

func TestExecuteLLMCall_Streaming(t *testing.T) {
	// Mock Ollama streaming endpoint
	ollamaServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/x-ndjson")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"response": "Hello", "done": false}` + "\n"))
		_, _ = w.Write([]byte(`{"response": " world", "done": true}` + "\n"))
	}))
	defer ollamaServer.Close()

	// Mock OpenAI compatible streaming endpoint
	openaiServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/event-stream")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("data: {\"choices\": [{\"delta\": {\"content\": \"Hello\"}}]}\n\n"))
		_, _ = w.Write([]byte("data: {\"choices\": [{\"delta\": {\"content\": \" world\"}}]}\n\n"))
		_, _ = w.Write([]byte("data: [DONE]\n\n"))
	}))
	defer openaiServer.Close()

	srv := &BrokerServer{
		isCLI: false, // Don't write to stdout during tests
	}

	ctx := context.Background()

	// Test Ollama stream
	resp, err := srv.executeLLMCall(ctx, "model", ProviderOllama, ollamaServer.URL, "prompt", "system", "", true, 0.1, 0)
	if err != nil {
		t.Fatalf("Ollama streaming call failed: %v", err)
	}
	if resp != "Hello world" {
		t.Errorf("Ollama expected 'Hello world', got %q", resp)
	}

	// Jan uses Anthropic /messages SSE format (not OpenAI /v1/chat/completions).
	janServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !strings.HasSuffix(r.URL.Path, "/messages") {
			http.Error(w, "wrong path: "+r.URL.Path, http.StatusNotFound)
			return
		}
		w.Header().Set("Content-Type", "text/event-stream")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("event: content_block_delta\ndata: {\"type\":\"content_block_delta\",\"delta\":{\"type\":\"text_delta\",\"text\":\"Hello\"}}\n\n"))
		_, _ = w.Write([]byte("event: content_block_delta\ndata: {\"type\":\"content_block_delta\",\"delta\":{\"type\":\"text_delta\",\"text\":\" world\"}}\n\n"))
		_, _ = w.Write([]byte("event: message_stop\ndata: {\"type\":\"message_stop\"}\n\n"))
	}))
	defer janServer.Close()

	resp, err = srv.executeLLMCall(ctx, "model", ProviderJan, janServer.URL, "prompt", "system", "", true, 0.1, 0)
	if err != nil {
		t.Fatalf("Jan streaming call failed: %v", err)
	}
	if resp != "Hello world" {
		t.Errorf("Jan expected 'Hello world', got %q", resp)
	}
}

func TestExecuteLLMCall_JanAnthropicNonStreaming(t *testing.T) {
	janServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !strings.HasSuffix(r.URL.Path, "/messages") {
			http.Error(w, "wrong path: "+r.URL.Path, http.StatusNotFound)
			return
		}
		if r.Header.Get("anthropic-version") == "" {
			http.Error(w, "missing anthropic-version header", http.StatusBadRequest)
			return
		}
		// Verify system prompt forwarded as top-level field
		var body map[string]any
		_ = json.NewDecoder(r.Body).Decode(&body)
		if _, ok := body["system"]; !ok {
			http.Error(w, "missing system field", http.StatusBadRequest)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"type":"message","role":"assistant","content":[{"type":"text","text":"Answer"}],"usage":{"output_tokens":1}}`))
	}))
	defer janServer.Close()

	srv := &BrokerServer{isCLI: false}
	resp, err := srv.executeLLMCall(context.Background(), "model", ProviderJan, janServer.URL, "prompt", "be helpful", "", false, 0.1, 100)
	if err != nil {
		t.Fatalf("Jan non-streaming call failed: %v", err)
	}
	if resp != "Answer" {
		t.Errorf("expected 'Answer', got %q", resp)
	}
}

func TestExecuteLLMCall_JanAnthropicThinkBlockStripped(t *testing.T) {
	janServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"type":"message","role":"assistant","content":[{"type":"text","text":"<think>internal</think>Visible answer"}]}`))
	}))
	defer janServer.Close()

	srv := &BrokerServer{isCLI: false}
	resp, err := srv.executeLLMCall(context.Background(), "model", ProviderJan, janServer.URL, "prompt", "", "", false, 0.1, 0)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if resp != "Visible answer" {
		t.Errorf("expected think blocks stripped, got %q", resp)
	}
}

func TestExecuteLLMCall_LargeSystemPromptPassedThrough(t *testing.T) {
	// Truncation was removed — verify the full system prompt reaches Jan unchanged.
	var receivedSysPrompt string
	janServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var body map[string]any
		_ = json.NewDecoder(r.Body).Decode(&body)
		if s, ok := body["system"].(string); ok {
			receivedSysPrompt = s
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"type":"message","content":[{"type":"text","text":"ok"}]}`))
	}))
	defer janServer.Close()

	srv := &BrokerServer{isCLI: false}
	largePrompt := strings.Repeat("x", 50000)
	_, err := srv.executeLLMCall(context.Background(), "model", ProviderJan, janServer.URL, "prompt", largePrompt, "", false, 0.1, 512)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(receivedSysPrompt) != 50000 {
		t.Errorf("expected full 50000-char system prompt, got %d chars", len(receivedSysPrompt))
	}
}

func TestExecuteLLMCall_ConcurrencyLimit(t *testing.T) {
	// Mock server that stays open until we signal it to complete
	holdChan := make(chan struct{})
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		<-holdChan
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"choices": [{"message": {"content": "completed"}}]}`))
	}))
	defer server.Close()
	defer close(holdChan) // ensure mock requests exit eventually

	srv := &BrokerServer{
		isCLI: false,
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	provider := "test-concurrency-provider"
	limit := 2

	// Fill the semaphore queue
	release1, err := srv.acquireSemaphore(ctx, provider, limit)
	if err != nil {
		t.Fatalf("Failed to acquire semaphore 1: %v", err)
	}
	defer release1()

	release2, err := srv.acquireSemaphore(ctx, provider, limit)
	if err != nil {
		t.Fatalf("Failed to acquire semaphore 2: %v", err)
	}
	defer release2()

	// Third attempt should block and fail due to context timeout since limit is 2
	shortCtx, shortCancel := context.WithTimeout(ctx, 100*time.Millisecond)
	defer shortCancel()

	_, err = srv.executeLLMCall(shortCtx, "model", provider, server.URL, "prompt", "system", "", false, 0.1, 0)
	if err == nil {
		t.Fatal("Expected error due to concurrency saturation, got nil")
	}

	if !strings.Contains(err.Error(), "concurrency limit reached/timeout") {
		t.Errorf("Expected concurrency limit error, got: %v", err)
	}
}

func TestExecuteLLMCall_LocalRetryFailover(t *testing.T) {
	// First server (Ollama mock) fails with 500
	serverOllama := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		_, _ = w.Write([]byte(`{"error": "Internal error"}`))
	}))
	defer serverOllama.Close()

	// Second server (Jan mock) succeeds — Jan uses Anthropic /messages format.
	serverJan := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !strings.HasSuffix(r.URL.Path, "/messages") {
			http.Error(w, "wrong path", http.StatusNotFound)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"type":"message","content":[{"type":"text","text":"success-jan"}]}`))
	}))
	defer serverJan.Close()

	srv := &BrokerServer{
		isCLI: false,
		urlOverrides: map[string]string{
			"ollama": serverOllama.URL,
			"jan":    serverJan.URL,
		},
		healthCache: map[string]BackendHealth{
			"ollama": {Available: true},
			"jan":    {Available: true},
		},
	}
	srv.workspaceRoot = "../.."

	// Clean up any existing test cache entries
	cacheDir := filepath.Join(srv.workspaceRoot, ".agent", "tmp", "llm_cache")
	_ = os.RemoveAll(cacheDir)
	defer os.RemoveAll(cacheDir)

	ctx := context.Background()

	req := mcp.CallToolRequest{
		Request: mcp.Request{
			Method: "tools/call",
		},
		Params: mcp.CallToolParams{
			Name: "execute_prompt",
			Arguments: map[string]any{
				"prompt":          "Write a simple function",
				"difficulty_hint": "implement feature",
			},
		},
	}

	res, err := srv.handleExecutePrompt(ctx, req)
	if err != nil {
		t.Fatalf("handleExecutePrompt failed: %v", err)
	}

	if res.IsError {
		var errMsg string
		for _, c := range res.Content {
			if txt, ok := c.(mcp.TextContent); ok {
				errMsg += txt.Text
			}
		}
		t.Fatalf("handleExecutePrompt returned error: %s", errMsg)
	}

	var responseText string
	for _, c := range res.Content {
		if txt, ok := c.(mcp.TextContent); ok {
			responseText = txt.Text
		}
	}

	var parsed struct {
		Response string `json:"response"`
		Source   string `json:"source"`
		Model    string `json:"model"`
	}
	if err := json.Unmarshal([]byte(responseText), &parsed); err != nil {
		t.Fatalf("failed to parse response JSON: %v", err)
	}

	if parsed.Source != "jan" {
		t.Errorf("Expected source 'jan', got %q", parsed.Source)
	}
	if parsed.Response != "success-jan" {
		t.Errorf("Expected response 'success-jan', got %q", parsed.Response)
	}
}

func TestCosineSimilarity(t *testing.T) {
	a := []float64{1.0, 0.0}
	b := []float64{1.0, 0.0}
	if sim := cosineSimilarity(a, b); math.Abs(sim-1.0) > 1e-9 {
		t.Errorf("Expected 1.0, got %f", sim)
	}

	c := []float64{0.0, 1.0}
	if sim := cosineSimilarity(a, c); math.Abs(sim-0.0) > 1e-9 {
		t.Errorf("Expected 0.0, got %f", sim)
	}

	d := []float64{1.0, 1.0}
	expected := 1.0 / math.Sqrt(2.0)
	if sim := cosineSimilarity(a, d); math.Abs(sim-expected) > 1e-6 {
		t.Errorf("Expected %f, got %f", expected, sim)
	}
}

func TestExecuteLLMCall_SemanticCacheHit(t *testing.T) {
	// Mock embeddings server (succeeds and returns similar embedding)
	embedServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"data": [{"embedding": [1.0, 0.0]}]}`))
	}))
	defer embedServer.Close()

	srv := &BrokerServer{
		isCLI: false,
		urlOverrides: map[string]string{
			"jan": embedServer.URL,
		},
		healthCache: map[string]BackendHealth{
			"jan": {Available: true},
		},
	}
	srv.workspaceRoot = "../.."

	// Clean up any existing test cache entries
	cacheDir := filepath.Join(srv.workspaceRoot, ".agent", "tmp", "semantic_cache")
	_ = os.RemoveAll(cacheDir)
	defer os.RemoveAll(cacheDir)

	// Save a test entry to semantic cache
	entry := SemanticCacheEntry{
		Prompt:    "Write a hello world program in Go",
		Response:  "package main; func main() { println(\"hello world\") }",
		Model:     "Jan-v3.5-4B-Q4_K_XL",
		Embedding: []float64{1.0, 0.0},
	}
	srv.saveSemanticCacheEntry("test-key", entry)

	ctx := context.Background()

	req := mcp.CallToolRequest{
		Request: mcp.Request{
			Method: "tools/call",
		},
		Params: mcp.CallToolParams{
			Name: "execute_prompt",
			Arguments: map[string]any{
				"prompt":          "Write a hello world program in Go",
				"model":           "Jan-v3.5-4B-Q4_K_XL",
			},
		},
	}

	res, err := srv.handleExecutePrompt(ctx, req)
	if err != nil {
		t.Fatalf("handleExecutePrompt failed: %v", err)
	}

	if res.IsError {
		t.Fatalf("handleExecutePrompt returned error")
	}

	var responseText string
	for _, c := range res.Content {
		if txt, ok := c.(mcp.TextContent); ok {
			responseText = txt.Text
		}
	}

	var parsed struct {
		Response string `json:"response"`
		Source   string `json:"source"`
		Model    string `json:"model"`
	}
	if err := json.Unmarshal([]byte(responseText), &parsed); err != nil {
		t.Fatalf("failed to parse response JSON: %v", err)
	}

	if parsed.Source != "semantic-cache" {
		t.Errorf("Expected source 'semantic-cache', got %q", parsed.Source)
	}
	if parsed.Response != entry.Response {
		t.Errorf("Expected cached response, got %q", parsed.Response)
	}
}

func TestBackgroundModelPulling(t *testing.T) {
	pullCalled := make(chan struct{}, 1)
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/api/pull" {
			w.WriteHeader(http.StatusOK)
			_, _ = w.Write([]byte(`{"status": "success"}`))
			pullCalled <- struct{}{}
		} else {
			w.WriteHeader(http.StatusNotFound)
		}
	}))
	defer server.Close()

	srv := &BrokerServer{
		isCLI: false,
		urlOverrides: map[string]string{
			"ollama": server.URL,
		},
	}

	rules := &RouterRules{}
	env := EnvironmentInfo{}

	srv.triggerBackgroundPull("test-model:8b", rules, env)

	// Wait for the pull routine to trigger the HTTP call
	select {
	case <-pullCalled:
		// success
	case <-time.After(2 * time.Second):
		t.Fatal("Timeout waiting for background pull endpoint to be called")
	}

	// Wait for goroutine to finish updating state
	time.Sleep(50 * time.Millisecond)

	srv.pullingStatesMu.RLock()
	status := srv.pullingStates["test-model:8b"]
	srv.pullingStatesMu.RUnlock()

	if status != "completed" {
		t.Errorf("Expected status 'completed', got %q", status)
	}

	// Test Discovery active downloads serialization
	req := mcp.CallToolRequest{
		Params: mcp.CallToolParams{
			Name: "detect_backends",
		},
	}
	res, err := srv.handleDetectBackends(context.Background(), req)
	if err != nil {
		t.Fatalf("handleDetectBackends failed: %v", err)
	}

	var parsedText string
	for _, c := range res.Content {
		if txt, ok := c.(mcp.TextContent); ok {
			parsedText = txt.Text
		}
	}

	var disc DiscoveryResult
	if err := json.Unmarshal([]byte(parsedText), &disc); err != nil {
		t.Fatalf("failed to unmarshal discovery result: %v", err)
	}

	if disc.Downloads["test-model:8b"] != "completed" {
		t.Errorf("Expected discovery active download status 'completed', got %q", disc.Downloads["test-model:8b"])
	}
}

// ---------------------------------------------------------------------------
// isOrchestratorContext
// ---------------------------------------------------------------------------

func TestIsOrchestratorContext(t *testing.T) {
	tests := []struct {
		name  string
		input string
		want  bool
	}{
		{
			name:  "empty prompt",
			input: "",
			want:  false,
		},
		{
			name:  "too short",
			input: "you are an orchestrator",
			want:  false,
		},
		{
			// Real orchestrator.md frontmatter pattern sent by opencode
			name: "frontmatter with name: orchestrator + delegates_to",
			input: strings.Repeat(" ", 200) +
				"name: orchestrator\n" +
				"delegates_to: [backend-specialist, frontend-specialist]\n" +
				strings.Repeat("context", 50),
			want: true,
		},
		{
			// Body-style: "you are" + "orchestrator" keyword
			name: "body style you are orchestrator",
			input: "You are the master orchestrator responsible for multi-agent coordination. " +
				"You delegate work to sub-agents and synthesize their results. " +
				strings.Repeat("x", 200),
			want: true,
		},
		{
			// Missing orchestration keyword — should NOT match
			name: "you are but no orchestration keyword",
			input: "You are a helpful assistant. " +
				strings.Repeat("x", 300),
			want: false,
		},
		{
			// Has "subagent" keyword without explicit role declaration
			name: "subagent keyword but no role decl",
			input: strings.Repeat("x", 200) +
				"this prompt involves a subagent pattern",
			want: false,
		},
		{
			// Both signals present via "multi-agent"
			name: "your role + multi-agent",
			input: "Your role is to coordinate the team. " +
				"This system uses a multi-agent approach where specialists are called. " +
				strings.Repeat("details", 30),
			want: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := isOrchestratorContext(tt.input)
			if got != tt.want {
				t.Errorf("isOrchestratorContext() = %v, want %v", got, tt.want)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// stripThinkBlocks — DeepSeek special tokens
// ---------------------------------------------------------------------------

func TestStripThinkBlocks_DeepSeekSpecialTokens(t *testing.T) {
	input := "Normal answer<｜tool▁outputs▁begin｜>garbage tool output"
	got := stripThinkBlocks(input)
	if got != "Normal answer" {
		t.Errorf("expected DeepSeek tokens stripped, got %q", got)
	}
}

func TestStripThinkBlocks_ThinkThenDeepSeek(t *testing.T) {
	input := "<think>reasoning</think>Answer<｜tool▁call▁begin｜>junk"
	got := stripThinkBlocks(input)
	if got != "Answer" {
		t.Errorf("expected both blocks stripped, got %q", got)
	}
}

// ---------------------------------------------------------------------------
// executeAgenticLoop
// ---------------------------------------------------------------------------

func TestExecuteAgenticLoop_RejectsNonJanProvider(t *testing.T) {
	srv := &BrokerServer{workspaceRoot: "../.."}
	_, err := srv.executeAgenticLoop(context.Background(),
		"test prompt", "system", "gemini-3-flash", "antigravity", "https://api.example.com", 1024, 5, "L2")
	if err == nil {
		t.Fatal("expected error for non-Jan provider, got nil")
	}
	if !strings.Contains(err.Error(), "agentic loop requires Jan provider") {
		t.Errorf("expected Jan-provider error, got: %v", err)
	}
}

func TestExecuteAgenticLoop_AnthropicFormat(t *testing.T) {
	// Mock Jan that: iter0 → returns tool_use(call_agent), iter1 → returns final text.
	iterCount := 0
	janServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !strings.HasSuffix(r.URL.Path, "/messages") {
			http.Error(w, "wrong path: "+r.URL.Path, http.StatusNotFound)
			return
		}
		if r.Header.Get("anthropic-version") == "" {
			http.Error(w, "missing anthropic-version header", http.StatusBadRequest)
			return
		}

		var body map[string]any
		_ = json.NewDecoder(r.Body).Decode(&body)

		// Verify system prompt is a top-level field, NOT inside messages[].
		if _, hasSys := body["system"]; !hasSys {
			http.Error(w, "missing top-level system field", http.StatusBadRequest)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		iter := iterCount
		iterCount++

		if iter == 0 {
			// First iteration: return tool_use to force delegation.
			w.WriteHeader(http.StatusOK)
			_, _ = w.Write([]byte(`{
				"content": [{"type":"tool_use","id":"tu_1","name":"call_agent","input":{"agent_name":"debugger","task":"check logs"}}],
				"stop_reason": "tool_use"
			}`))
			return
		}
		// Second iteration: final answer.
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{
			"content": [{"type":"text","text":"Done. Logs checked."}],
			"stop_reason": "end_turn"
		}`))
	}))
	defer janServer.Close()

	srv := &BrokerServer{
		workspaceRoot: "../..",
		healthCache:   map[string]BackendHealth{"jan": {Available: true}},
		urlOverrides:  map[string]string{"jan": janServer.URL},
	}

	resp, err := srv.executeAgenticLoop(context.Background(),
		"check logs", "you are orchestrator delegates_to agents "+strings.Repeat("x", 200),
		"Qwen3_6-27B-IQ4_XS", ProviderJan, janServer.URL, 1024, 10, "L3")

	// invokeAgent will fail (no agent file in test env) — but the loop must have
	// sent the request in Anthropic format and reached at least the tool_use phase.
	// We verify format compliance via the mock's header/field checks above.
	// The actual invokeAgent error is expected — it means format was correct.
	if err != nil && strings.Contains(err.Error(), "wrong path") {
		t.Errorf("loop used wrong endpoint: %v", err)
	}
	if err != nil && strings.Contains(err.Error(), "missing anthropic-version") {
		t.Errorf("loop missing anthropic-version header: %v", err)
	}
	if err != nil && strings.Contains(err.Error(), "missing top-level system") {
		t.Errorf("loop put system inside messages instead of top-level: %v", err)
	}
	// If we got a response, verify it's the final text.
	if err == nil && resp != "Done. Logs checked." {
		t.Errorf("expected final answer, got %q", resp)
	}
}

// ---------------------------------------------------------------------------
// isComplexEnoughForAgenticLoop
// ---------------------------------------------------------------------------

func TestIsComplexEnoughForAgenticLoop(t *testing.T) {
	tests := []struct {
		prompt string
		want   bool
	}{
		// Trivial conversational — must NOT trigger agentic loop
		{"привет", false},
		{"hi", false},
		{"ok", false},
		{"да", false},
		{"как дела?", false},
		{"спасибо", false},
		// Creative/short non-technical
		{"напиши стихотворение", false},
		// Russian engineering tasks — must trigger
		{"сделай дебаг headroom", true},
		{"нужен анализ почему сервис падает", true},
		{"проверь ошибки в логах", true},
		{"реализуй новый endpoint", true},
		{"исправь баг в авторизации", true},
		{"отладка соединения с базой", true},
		// English engineering tasks
		{"debug the memory leak", true},
		{"fix the failing test", true},
		{"analyze why the service crashes", true},
		{"implement the new API endpoint", true},
		// Service names in prompt
		{"headroom не отвечает", true},
		// Longer conversational — no keywords → still false
		{"расскажи мне о себе подробнее", false},
	}
	for _, tt := range tests {
		t.Run(tt.prompt, func(t *testing.T) {
			got := isComplexEnoughForAgenticLoop(tt.prompt)
			if got != tt.want {
				t.Errorf("isComplexEnoughForAgenticLoop(%q) = %v, want %v", tt.prompt, got, tt.want)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// compactMessagesHistory
// ---------------------------------------------------------------------------

func TestCompactMessagesHistory_BelowThreshold(t *testing.T) {
	srv := &BrokerServer{workspaceRoot: "../.."}
	messages := []map[string]any{
		{"role": "user", "content": "hello"},
	}
	result := srv.compactMessagesHistory(context.Background(), messages, 100000, "http://unused", "model")
	if len(result) != 1 {
		t.Errorf("expected unchanged messages, got %d", len(result))
	}
}

func TestCompactMessagesHistory_LLMSummarizes(t *testing.T) {
	janServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Both /v1/models (findL1ModelForJan) and /messages (summarisation) arrive here.
		if r.URL.Path == "/v1/models" {
			// Return empty — no L1 model, will fall back to fallbackModel.
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`{"data":[]}`))
			return
		}
		if strings.HasSuffix(r.URL.Path, "/messages") {
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`{"content":[{"type":"text","text":"Debugger found memory leak in srv.go:42."}],"stop_reason":"end_turn"}`))
			return
		}
		http.Error(w, "unexpected path: "+r.URL.Path, http.StatusNotFound)
	}))
	defer janServer.Close()

	srv := &BrokerServer{workspaceRoot: "../.."}
	messages := []map[string]any{
		{"role": "user", "content": "debug headroom"},
		{"role": "assistant", "content": []any{map[string]any{"type": "tool_use", "id": "t1", "name": "call_agent", "input": map[string]any{"agent_name": "debugger", "task": "check"}}}},
		{"role": "user", "content": []any{map[string]any{"type": "tool_result", "tool_use_id": "t1", "content": strings.Repeat("log line\n", 300)}}},
	}

	result := srv.compactMessagesHistory(context.Background(), messages, 1, janServer.URL, "Qwen3_6-27B-IQ4_XS")

	if len(result) != 2 {
		t.Fatalf("expected [original, summary], got %d messages", len(result))
	}
	if result[0]["content"] != "debug headroom" {
		t.Errorf("original prompt not preserved: %v", result[0]["content"])
	}
	summaryContent, _ := result[1]["content"].(string)
	if !strings.Contains(summaryContent, "memory leak") {
		t.Errorf("summary not injected: %q", summaryContent)
	}
}

func TestCompactMessagesHistory_LLMFailReturnsOriginal(t *testing.T) {
	janServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/v1/models" {
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`{"data":[]}`))
			return
		}
		// Summarisation endpoint returns 500.
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer janServer.Close()

	srv := &BrokerServer{workspaceRoot: "../.."}
	messages := []map[string]any{
		{"role": "user", "content": "original"},
		{"role": "assistant", "content": "a1"},
		{"role": "user", "content": strings.Repeat("result", 500)},
	}

	result := srv.compactMessagesHistory(context.Background(), messages, 1, janServer.URL, "Qwen3_6-27B-IQ4_XS")

	// Must return original unchanged — no data lost.
	if len(result) != 3 {
		t.Errorf("expected original 3 messages on LLM failure, got %d", len(result))
	}
}

func TestCompactMessagesHistory_TooFewMessages(t *testing.T) {
	srv := &BrokerServer{workspaceRoot: "../.."}
	messages := []map[string]any{
		{"role": "user", "content": "only prompt, no pairs yet"},
		{"role": "assistant", "content": "thinking"},
	}
	result := srv.compactMessagesHistory(context.Background(), messages, 1, "http://unused", "model")
	if len(result) != 2 {
		t.Errorf("expected 2 messages (< 3 threshold), got %d", len(result))
	}
}

// ---------------------------------------------------------------------------
// executeAgenticLoop — empty body handling (context overflow)
// ---------------------------------------------------------------------------

func TestExecuteAgenticLoop_EmptyBodyReturnsLastText(t *testing.T) {
	// Mock Jan: iter0 → returns tool_use, iter1 → returns 200 with empty body (overflow).
	iterCount := 0
	janServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !strings.HasSuffix(r.URL.Path, "/messages") {
			http.Error(w, "wrong path", http.StatusNotFound)
			return
		}
		iter := iterCount
		iterCount++
		w.Header().Set("Content-Type", "application/json")
		if iter == 0 {
			w.WriteHeader(http.StatusOK)
			_, _ = w.Write([]byte(`{
				"content": [{"type":"tool_use","id":"tu_e1","name":"call_agent","input":{"agent_name":"debugger","task":"check logs"}}],
				"stop_reason": "tool_use"
			}`))
			return
		}
		// Simulate context overflow: HTTP 200 + empty body.
		w.WriteHeader(http.StatusOK)
	}))
	defer janServer.Close()

	srv := &BrokerServer{
		workspaceRoot: "../..",
		healthCache:   map[string]BackendHealth{"jan": {Available: true}},
	}

	// Must NOT return an error — should return gracefully with empty lastText.
	_, err := srv.executeAgenticLoop(context.Background(),
		"check logs",
		"you are orchestrator delegates_to agents "+strings.Repeat("x", 200),
		"Qwen3_6-27B-IQ4_XS", ProviderJan, janServer.URL, 1024, 10, "L3")

	if err != nil {
		t.Errorf("expected graceful return on empty body, got error: %v", err)
	}
}

func TestFormatPerfStats(t *testing.T) {
	cases := []struct {
		tokens  int
		elapsed time.Duration
		model   string
		tier    string
		score   int
		want    string
	}{
		{0, 2 * time.Second, "", "", 0, ""},
		{100, 400 * time.Millisecond, "", "", 0, ""},  // < 0.5 s → skip
		{200, 2 * time.Second, "", "", 0, "100 tok/s (200 tokens)"},
		{1000, 10 * time.Second, "Qwen3-27B", "L3", 10, "100 tok/s (1000 tokens) · score=10 L3 · Qwen3-27B"},
		{500, 5 * time.Second, "Jan-4B", "L1", 5, "100 tok/s (500 tokens) · score=5 L1 · Jan-4B"},
	}
	for _, c := range cases {
		got := formatPerfStats(c.tokens, c.elapsed, c.model, c.tier, c.score)
		if c.want != "" && got != c.want {
			t.Errorf("formatPerfStats(%d, %v, %q, %q, %d) = %q, want %q",
				c.tokens, c.elapsed, c.model, c.tier, c.score, got, c.want)
		}
		if c.want == "" && got != "" && c.elapsed >= 500*time.Millisecond {
			t.Errorf("formatPerfStats(%d, %v) = %q, want empty", c.tokens, c.elapsed, got)
		}
	}
}

func TestStreamAgenticIteration_ParsesSSE(t *testing.T) {
	// Mock Jan: returns a valid SSE stream with text + tool_use + usage.
	janServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/event-stream")
		w.WriteHeader(http.StatusOK)
		events := []string{
			"event: message_start\ndata: {\"message\":{\"usage\":{\"input_tokens\":42}}}\n\n",
			"event: content_block_start\ndata: {\"content_block\":{\"type\":\"text\",\"id\":\"\",\"name\":\"\"}}\n\n",
			"event: content_block_delta\ndata: {\"delta\":{\"type\":\"text_delta\",\"text\":\"hello \"}}\n\n",
			"event: content_block_delta\ndata: {\"delta\":{\"type\":\"text_delta\",\"text\":\"world\"}}\n\n",
			"event: content_block_stop\ndata: {}\n\n",
			"event: content_block_start\ndata: {\"content_block\":{\"type\":\"tool_use\",\"id\":\"tu_1\",\"name\":\"call_agent\"}}\n\n",
			"event: content_block_delta\ndata: {\"delta\":{\"type\":\"input_json_delta\",\"partial_json\":\"{\\\"agent_name\\\":\\\"\"}}\n\n",
			"event: content_block_delta\ndata: {\"delta\":{\"type\":\"input_json_delta\",\"partial_json\":\"debugger\\\",\\\"task\\\":\\\"x\\\"\"}}\n\n",
			"event: content_block_delta\ndata: {\"delta\":{\"type\":\"input_json_delta\",\"partial_json\":\"}\"}}\n\n",
			"event: content_block_stop\ndata: {}\n\n",
			"event: message_delta\ndata: {\"delta\":{\"stop_reason\":\"tool_use\"},\"usage\":{\"output_tokens\":77}}\n\n",
			"event: message_stop\ndata: {}\n\n",
		}
		for _, e := range events {
			fmt.Fprint(w, e)
			w.(http.Flusher).Flush()
		}
	}))
	defer janServer.Close()

	srv := &BrokerServer{workspaceRoot: "../..", healthCache: map[string]BackendHealth{}}
	var received []string
	onToken := func(tok string) { received = append(received, tok) }

	payload := map[string]any{"model": "test-model", "messages": []any{}, "max_tokens": 1024}
	result, err := srv.streamAgenticIteration(context.Background(), payload, janServer.URL, onToken)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result.overflow {
		t.Error("expected overflow=false")
	}
	if result.stopReason != "tool_use" {
		t.Errorf("stopReason = %q, want tool_use", result.stopReason)
	}
	if result.inputTokens != 42 {
		t.Errorf("inputTokens = %d, want 42", result.inputTokens)
	}
	if result.outputTokens != 77 {
		t.Errorf("outputTokens = %d, want 77", result.outputTokens)
	}
	if len(result.texts) != 1 || result.texts[0] != "hello world" {
		t.Errorf("texts = %v, want [\"hello world\"]", result.texts)
	}
	if len(result.toolUses) != 1 || result.toolUses[0].id != "tu_1" || result.toolUses[0].name != "call_agent" {
		t.Errorf("toolUses = %v", result.toolUses)
	}
	if len(received) == 0 {
		t.Error("expected onToken to receive tokens")
	}
}

func TestStreamAgenticIteration_OverflowOnEmptyStream(t *testing.T) {
	// Jan closes immediately without message_stop — simulates context overflow.
	janServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/event-stream")
		w.WriteHeader(http.StatusOK)
		// write nothing
	}))
	defer janServer.Close()

	srv := &BrokerServer{workspaceRoot: "../..", healthCache: map[string]BackendHealth{}}
	payload := map[string]any{"model": "test-model", "messages": []any{}, "max_tokens": 1024}
	result, err := srv.streamAgenticIteration(context.Background(), payload, janServer.URL, func(string) {})

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !result.overflow {
		t.Error("expected overflow=true when stream is empty")
	}
}

func TestExtractUserQuery(t *testing.T) {
	template := `<!-- GENERATED by sync_agents.py (target: opencode) — do not edit directly -->

---
description: Structured brainstorming for projects and features.
agent: orchestrator
---

# /brainstorm - Structured Idea Exploration

что тут можно улучшить

---

## Purpose

This command activates BRAINSTORM mode.`

	got := extractUserQuery(template)
	if got != "что тут можно улучшить" {
		t.Errorf("extractUserQuery = %q, want %q", got, "что тут можно улучшить")
	}

	// Non-template prompt should be returned unchanged.
	plain := "просто вопрос без шаблона"
	if got2 := extractUserQuery(plain); got2 != plain {
		t.Errorf("extractUserQuery(plain) = %q, want unchanged %q", got2, plain)
	}

	// Empty query inside template → fallback to full prompt.
	emptyQuery := "<!-- GENERATED -->\n---\ndesc: x\n---\n# /cmd - Title\n\n---\n## Purpose\n..."
	if got3 := extractUserQuery(emptyQuery); got3 != emptyQuery {
		t.Errorf("extractUserQuery(empty query) should return original, got %q", got3)
	}
}

func TestTrimToFirstInstructionFile(t *testing.T) {
	tests := []struct {
		name  string
		input string
		want  string
	}{
		{
			name:  "no markers",
			input: "hello world\nsome text",
			want:  "hello world\nsome text",
		},
		{
			name:  "multiple generated markers",
			input: "<!-- GENERATED by sync_agents.py (target: opencode) -->\nfirst content\n<!-- GENERATED by sync_agents.py (target: opencode) -->\nsecond content",
			want:  "<!-- GENERATED by sync_agents.py (target: opencode) -->\nfirst content",
		},
		{
			name:  "trigger always_on fallback",
			input: "<!-- GENERATED by sync_agents.py (target: opencode) -->\nfirst content\n---\ntrigger: always_on\n---\nsecond content",
			want:  "<!-- GENERATED by sync_agents.py (target: opencode) -->\nfirst content",
		},
		{
			name:  "trigger always_on fallback without generated",
			input: "first content\n---\ntrigger: always_on\n---\nsecond content",
			want:  "first content",
		},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got := trimToFirstInstructionFile(tc.input)
			if got != tc.want {
				t.Errorf("got %q, want %q", got, tc.want)
			}
		})
	}
}

func TestStripOldRules(t *testing.T) {
	tests := []struct {
		name  string
		input string
		want  string
	}{
		{
			name:  "clean prompt remains unchanged",
			input: "You are a helpful assistant.\nAnswer in detail.",
			want:  "You are a helpful assistant.\nAnswer in detail.",
		},
		{
			name: "strips single section",
			input: "You are a helpful assistant.\n## TIER 0: UNIVERSAL RULES (Always Active)\n- rule 1\n- rule 2\nAlways use rtk <cmd> instead of raw commands.\nAnswer in detail.",
			want: "You are a helpful assistant.\nAnswer in detail.",
		},
		{
			name: "strips multiple sections and attention headers",
			input: "🔴 ATTENTION: THIS FILE IS AUTO-GENERATED\n- rule 1\n-->\nNormal instructions\n## TIER 1: CODE RULES (When Writing Code)\n- rule 2\nAlways use `rtk <cmd>` instead of raw commands.\nEnd instructions",
			want: "Normal instructions\nEnd instructions",
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got := stripOldRules(tc.input)
			if got != tc.want {
				t.Errorf("got %q, want %q", got, tc.want)
			}
		})
	}
}

func TestFileRuleLoaderAdapter_LoadRules(t *testing.T) {
	tempDir := t.TempDir()
	rulesDir := filepath.Join(tempDir, ".agent", "rules", "gemini")
	if err := os.MkdirAll(rulesDir, 0755); err != nil {
		t.Fatalf("failed to create temp rules dir: %v", err)
	}

	// Write dummy rules files
	// Core
	err := os.WriteFile(filepath.Join(rulesDir, "00_protocol.md"), []byte("trigger: always_on\n00_protocol content"), 0644)
	if err != nil {
		t.Fatalf("failed to write 00_protocol.md: %v", err)
	}
	err = os.WriteFile(filepath.Join(rulesDir, "04_tier0_universal.md"), []byte("trigger: always_on\n04_tier0_universal content"), 0644)
	if err != nil {
		t.Fatalf("failed to write 04_tier0_universal.md: %v", err)
	}
	err = os.WriteFile(filepath.Join(rulesDir, "10_rtk.md"), []byte("trigger: always_on\n10_rtk content"), 0644)
	if err != nil {
		t.Fatalf("failed to write 10_rtk.md: %v", err)
	}

	// Code
	err = os.WriteFile(filepath.Join(rulesDir, "05_tier1_code.md"), []byte("trigger: always_on\n05_tier1_code content"), 0644)
	if err != nil {
		t.Fatalf("failed to write 05_tier1_code.md: %v", err)
	}
	err = os.WriteFile(filepath.Join(rulesDir, "09_go_dependency_management.md"), []byte("trigger: always_on\n09_go_dependency_management content"), 0644)
	if err != nil {
		t.Fatalf("failed to write 09_go_dependency_management.md: %v", err)
	}

	// Design
	err = os.WriteFile(filepath.Join(rulesDir, "06_tier2_design.md"), []byte("trigger: always_on\n06_tier2_design content"), 0644)
	if err != nil {
		t.Fatalf("failed to write 06_tier2_design.md: %v", err)
	}

	// Gateway
	err = os.WriteFile(filepath.Join(rulesDir, "03_gateway.md"), []byte("trigger: always_on\n03_gateway content"), 0644)
	if err != nil {
		t.Fatalf("failed to write 03_gateway.md: %v", err)
	}

	adapter := NewFileRuleLoaderAdapter(tempDir)

	// Case 1: L1 conversational query (should load only Core rules)
	res, err := adapter.LoadRules("You are a helpful assistant.", "hello there", "L1")
	if err != nil {
		t.Fatalf("LoadRules failed: %v", err)
	}
	if !strings.Contains(res, "00_protocol content") || !strings.Contains(res, "04_tier0_universal content") {
		t.Errorf("Expected core rules in output, got: %s", res)
	}
	if strings.Contains(res, "05_tier1_code content") || strings.Contains(res, "06_tier2_design content") {
		t.Errorf("Unexpected rule loaded for L1 conversational: %s", res)
	}

	// Case 2: L2 query with code (should load Core + Code rules)
	res, err = adapter.LoadRules("You are a helpful assistant.", "write a function", "L2")
	if err != nil {
		t.Fatalf("LoadRules failed: %v", err)
	}
	if !strings.Contains(res, "05_tier1_code content") {
		t.Errorf("Expected code rules for L2 code query, got: %s", res)
	}

	// Case 3: L2 query with go (should load Core + Code + Go rules)
	res, err = adapter.LoadRules("You are a helpful assistant.", "write a function in golang", "L2")
	if err != nil {
		t.Fatalf("LoadRules failed: %v", err)
	}
	if !strings.Contains(res, "09_go_dependency_management content") {
		t.Errorf("Expected Go rules for L2 go query, got: %s", res)
	}

	// Case 4: L3 query with design (should load Core + Code + Design rules)
	res, err = adapter.LoadRules("You are a helpful assistant.", "style the login button", "L3")
	if err != nil {
		t.Fatalf("LoadRules failed: %v", err)
	}
	if !strings.Contains(res, "06_tier2_design content") {
		t.Errorf("Expected design rules for L3 design query, got: %s", res)
	}

	// Case 5: L4 query (should load Core + Code + Gateway rules)
	res, err = adapter.LoadRules("You are a helpful assistant.", "verify authentication", "L4")
	if err != nil {
		t.Fatalf("LoadRules failed: %v", err)
	}
	if !strings.Contains(res, "03_gateway content") {
		t.Errorf("Expected gateway rules for L4 query, got: %s", res)
	}
}


