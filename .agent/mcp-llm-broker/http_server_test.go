package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func setupTestServer(t *testing.T) *BrokerServer {
	t.Helper()
	return &BrokerServer{
		workspaceRoot: t.TempDir(),
		semaphores:    make(map[string]chan struct{}),
		healthCache:   make(map[string]BackendHealth),
		pullingStates: make(map[string]string),
	}
}

// ---------------------------------------------------------------------------
// extractPromptFromMessages
// ---------------------------------------------------------------------------

func TestExtractPromptFromMessages(t *testing.T) {
	tests := []struct {
		name           string
		messages       []ChatMessage
		wantPrompt     string
		wantSystem     string
	}{
		{
			name: "user only",
			messages: []ChatMessage{
				{Role: "user", Content: "hello"},
			},
			wantPrompt: "hello",
			wantSystem: "",
		},
		{
			name: "system + user",
			messages: []ChatMessage{
				{Role: "system", Content: "be helpful"},
				{Role: "user", Content: "hi"},
			},
			wantPrompt: "hi",
			wantSystem: "be helpful",
		},
		{
			name: "multiple users picks last",
			messages: []ChatMessage{
				{Role: "user", Content: "first"},
				{Role: "assistant", Content: "ok"},
				{Role: "user", Content: "second"},
			},
			wantPrompt: "second",
			wantSystem: "",
		},
		{
			name: "system + multiple users",
			messages: []ChatMessage{
				{Role: "system", Content: "sys1"},
				{Role: "user", Content: "hello"},
				{Role: "assistant", Content: "world"},
				{Role: "user", Content: "final"},
			},
			wantPrompt: "final",
			wantSystem: "sys1",
		},
		{
			name: "no user message returns empty",
			messages: []ChatMessage{
				{Role: "system", Content: "sys"},
			},
			wantPrompt: "",
			wantSystem: "sys",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			prompt, sys := extractPromptFromMessages(tt.messages)
			if prompt != tt.wantPrompt {
				t.Errorf("prompt = %q, want %q", prompt, tt.wantPrompt)
			}
			if sys != tt.wantSystem {
				t.Errorf("systemPrompt = %q, want %q", sys, tt.wantSystem)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// GET /healthz
// ---------------------------------------------------------------------------

func TestHealthz(t *testing.T) {
	srv := setupTestServer(t)

	// Pre-fill health cache
	srv.healthCache[ProviderOllama] = BackendHealth{Available: true}
	srv.healthCache[ProviderJan] = BackendHealth{Available: false}
	srv.healthCache[ProviderLMStudio] = BackendHealth{Available: true}

	req := httptest.NewRequest("GET", "/healthz", nil)
	w := httptest.NewRecorder()

	handler := corsMiddleware(http.HandlerFunc(srv.handleHealthz))
	handler.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	var resp map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to parse response: %v", err)
	}

	if resp["status"] != "ok" {
		t.Errorf("expected status 'ok', got %q", resp["status"])
	}

	backends, ok := resp["backends"].(map[string]interface{})
	if !ok {
		t.Fatal("backends not present")
	}
	if backends["ollama"] != true {
		t.Error("expected ollama: true")
	}
	if backends["jan"] != false {
		t.Error("expected jan: false")
	}
}

func TestHealthzDegraded(t *testing.T) {
	srv := setupTestServer(t)
	// All backends unavailable
	srv.healthCache[ProviderOllama] = BackendHealth{Available: false}
	srv.healthCache[ProviderJan] = BackendHealth{Available: false}

	req := httptest.NewRequest("GET", "/healthz", nil)
	w := httptest.NewRecorder()

	handler := corsMiddleware(http.HandlerFunc(srv.handleHealthz))
	handler.ServeHTTP(w, req)

	var resp map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to parse response: %v", err)
	}

	if resp["status"] != "degraded" {
		t.Errorf("expected status 'degraded', got %q", resp["status"])
	}
}

func TestHealthzMethodNotAllowed(t *testing.T) {
	srv := setupTestServer(t)
	req := httptest.NewRequest("POST", "/healthz", nil)
	w := httptest.NewRecorder()
	handler := corsMiddleware(http.HandlerFunc(srv.handleHealthz))
	handler.ServeHTTP(w, req)

	if w.Code != http.StatusMethodNotAllowed {
		t.Errorf("expected 405, got %d", w.Code)
	}
}

// ---------------------------------------------------------------------------
// POST /v1/chat/completions
// ---------------------------------------------------------------------------

func TestChatCompletionsBadMethod(t *testing.T) {
	srv := setupTestServer(t)
	req := httptest.NewRequest("GET", "/v1/chat/completions", nil)
	w := httptest.NewRecorder()
	handler := corsMiddleware(http.HandlerFunc(srv.handleChatCompletions))
	handler.ServeHTTP(w, req)

	if w.Code != http.StatusMethodNotAllowed {
		t.Errorf("expected 405, got %d", w.Code)
	}
}

func TestChatCompletionsInvalidJSON(t *testing.T) {
	srv := setupTestServer(t)
	req := httptest.NewRequest("POST", "/v1/chat/completions",
		strings.NewReader(`not-json`))
	w := httptest.NewRecorder()
	handler := corsMiddleware(http.HandlerFunc(srv.handleChatCompletions))
	handler.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", w.Code)
	}

	var resp ChatCompletionResponse
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to parse: %v", err)
	}
	if resp.Error == nil {
		t.Fatal("expected error in response")
	}
}

func TestChatCompletionsNoUserMessage(t *testing.T) {
	srv := setupTestServer(t)
	body := `{"model":"test","messages":[{"role":"assistant","content":"hi"}]}`
	req := httptest.NewRequest("POST", "/v1/chat/completions",
		strings.NewReader(body))
	w := httptest.NewRecorder()
	handler := corsMiddleware(http.HandlerFunc(srv.handleChatCompletions))
	handler.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", w.Code)
	}
}

// ---------------------------------------------------------------------------
// CORS middleware
// ---------------------------------------------------------------------------

func TestCORSOptions(t *testing.T) {
	handler := corsMiddleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))

	req := httptest.NewRequest("OPTIONS", "/v1/chat/completions", nil)
	w := httptest.NewRecorder()
	handler.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("expected 200 for OPTIONS, got %d", w.Code)
	}
	if h := w.Header().Get("Access-Control-Allow-Origin"); h != "*" {
		t.Errorf("expected CORS origin *, got %q", h)
	}
}

func TestCORSHeaders(t *testing.T) {
	handler := corsMiddleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))

	req := httptest.NewRequest("GET", "/healthz", nil)
	w := httptest.NewRecorder()
	handler.ServeHTTP(w, req)

	if h := w.Header().Get("Access-Control-Allow-Origin"); h != "*" {
		t.Errorf("expected CORS header, got %q", h)
	}
}

// ---------------------------------------------------------------------------
// Response builders
// ---------------------------------------------------------------------------

func TestBuildChatCompletionResponse(t *testing.T) {
	result := &ExecutionResult{
		Response: "Hello world",
		Model:    "test-model",
	}
	usage := ResponseUsage{PromptTokens: 5, CompletionTokens: 8, TotalTokens: 13}

	resp := buildChatCompletionResponse(result, usage)
	if resp.Object != "chat.completion" {
		t.Errorf("object = %q", resp.Object)
	}
	if len(resp.Choices) != 1 {
		t.Fatalf("expected 1 choice, got %d", len(resp.Choices))
	}
	if resp.Choices[0].Message.Content != "Hello world" {
		t.Errorf("content = %q", resp.Choices[0].Message.Content)
	}
	if resp.Model != "test-model" {
		t.Errorf("model = %q", resp.Model)
	}
	if resp.Usage.TotalTokens != 13 {
		t.Errorf("total tokens = %d", resp.Usage.TotalTokens)
	}
}

func TestBuildTokenUsage(t *testing.T) {
	usage := buildTokenUsage("hello world", "hi there")
	if usage.PromptTokens <= 0 {
		t.Errorf("prompt tokens should be > 0")
	}
	if usage.CompletionTokens <= 0 {
		t.Errorf("completion tokens should be > 0")
	}
	if usage.TotalTokens != usage.PromptTokens+usage.CompletionTokens {
		t.Error("total should equal prompt + completion")
	}
}

func TestBuildErrorResponse(t *testing.T) {
	resp := buildErrorResponse(400, "bad request")
	if resp.Error == nil {
		t.Fatal("expected error")
	}
	if resp.Error.Message != "bad request" {
		t.Errorf("message = %q", resp.Error.Message)
	}
	if resp.Error.Code != "400" {
		t.Errorf("code = %q", resp.Error.Code)
	}
}

// ---------------------------------------------------------------------------
// Integration: healthz via HTTP test server
// ---------------------------------------------------------------------------

func TestHealthzViaHTTPServer(t *testing.T) {
	srv := setupTestServer(t)
	srv.healthCache[ProviderOllama] = BackendHealth{Available: true}

	// Create a test HTTP server wrapping the handler
	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", srv.handleHealthz)
	handler := corsMiddleware(mux)

	ts := httptest.NewServer(handler)
	defer ts.Close()

	resp, err := http.Get(ts.URL + "/healthz")
	if err != nil {
		t.Fatalf("GET /healthz failed: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		t.Errorf("expected 200, got %d", resp.StatusCode)
	}

	var body map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&body); err != nil {
		t.Fatalf("failed to decode: %v", err)
	}
	if body["status"] != "ok" {
		t.Errorf("status = %q", body["status"])
	}
}

// ---------------------------------------------------------------------------
// stripThinkBlocks
// ---------------------------------------------------------------------------

func TestStripThinkBlocks(t *testing.T) {
	tests := []struct {
		name  string
		input string
		want  string
	}{
		{"no think block", "hello world", "hello world"},
		{"complete think block", "<think>reasoning</think>answer", "answer"},
		{"think block with spaces", "<think> internal </think> visible", "visible"},
		{"unclosed think block trims tail", "<think>never closed", ""},
		{"multiple think blocks", "<think>a</think>first<think>b</think>second", "firstsecond"},
		{"nested-like text", "pre<think>mid</think>post", "prepost"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := stripThinkBlocks(tt.input)
			if got != tt.want {
				t.Errorf("stripThinkBlocks(%q) = %q, want %q", tt.input, got, tt.want)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// thinkFilter — real-time streaming think-block removal
// ---------------------------------------------------------------------------

func TestThinkFilter_NoThinkBlock(t *testing.T) {
	var out strings.Builder
	f := &thinkFilter{out: func(s string) { out.WriteString(s) }}
	f.feed("hello ")
	f.feed("world")
	f.flush()
	if out.String() != "hello world" {
		t.Errorf("expected 'hello world', got %q", out.String())
	}
}

func TestThinkFilter_CompleteBlock(t *testing.T) {
	var out strings.Builder
	f := &thinkFilter{out: func(s string) { out.WriteString(s) }}
	f.feed("<think>internal reasoning</think>")
	f.feed("visible answer")
	f.flush()
	if out.String() != "visible answer" {
		t.Errorf("expected 'visible answer', got %q", out.String())
	}
}

func TestThinkFilter_SplitAcrossChunks(t *testing.T) {
	var out strings.Builder
	f := &thinkFilter{out: func(s string) { out.WriteString(s) }}
	// Think open tag split across chunks
	f.feed("<th")
	f.feed("ink>hidden</think>")
	f.feed("shown")
	f.flush()
	if out.String() != "shown" {
		t.Errorf("expected 'shown', got %q", out.String())
	}
}

func TestThinkFilter_UnclosedBlock(t *testing.T) {
	var out strings.Builder
	f := &thinkFilter{out: func(s string) { out.WriteString(s) }}
	f.feed("prefix")
	f.feed("<think>never closed content")
	f.flush()
	// Everything after <think> should be suppressed
	if out.String() != "prefix" {
		t.Errorf("expected 'prefix', got %q", out.String())
	}
}

func TestBuildAnthropicMessages_Basic(t *testing.T) {
	msgs := []ChatMessage{
		{Role: "system", Content: "be helpful"},
		{Role: "user", Content: "hello"},
		{Role: "assistant", Content: "hi there"},
		{Role: "user", Content: "how are you"},
	}
	result := buildAnthropicMessages(msgs, 0)
	if len(result) != 3 {
		t.Fatalf("expected 3 messages (no system), got %d", len(result))
	}
	if result[0]["role"] != "user" || result[0]["content"] != "hello" {
		t.Errorf("wrong first message: %v", result[0])
	}
	if result[2]["role"] != "user" || result[2]["content"] != "how are you" {
		t.Errorf("wrong last message: %v", result[2])
	}
}

func TestBuildAnthropicMessages_TruncatesOldTurns(t *testing.T) {
	msgs := []ChatMessage{
		{Role: "user", Content: "old message that is quite long indeed"},
		{Role: "assistant", Content: "old response"},
		{Role: "user", Content: "new"},
	}
	// maxChars=10 — only the newest user message fits
	result := buildAnthropicMessages(msgs, 10)
	if len(result) != 1 {
		t.Fatalf("expected 1 message after truncation, got %d: %v", len(result), result)
	}
	if result[0]["content"] != "new" {
		t.Errorf("expected 'new', got %v", result[0]["content"])
	}
}

func TestBuildAnthropicMessages_EndsWithUser(t *testing.T) {
	msgs := []ChatMessage{
		{Role: "user", Content: "q"},
		{Role: "assistant", Content: "a"},
	}
	result := buildAnthropicMessages(msgs, 0)
	// Last message is assistant — must be trimmed so result ends with user.
	if len(result) != 1 || result[0]["role"] != "user" {
		t.Errorf("expected single user message, got %v", result)
	}
}

func TestBuildAnthropicMessages_ToolResultBecomesUser(t *testing.T) {
	msgs := []ChatMessage{
		{Role: "user", Content: "run ls"},
		{Role: "tool", ToolCallID: "tc_1", Content: "file1.txt\nfile2.txt"},
		{Role: "user", Content: "summarize"},
	}
	result := buildAnthropicMessages(msgs, 0)
	// Three consecutive user turns must be merged into one message.
	// Mixed text + structured → array content.
	if len(result) != 1 {
		t.Fatalf("expected 1 merged user message (Anthropic alternation), got %d: %v", len(result), result)
	}
	if result[0]["role"] != "user" {
		t.Errorf("expected user role, got %v", result[0]["role"])
	}
	// Content must be an array (mixed plain text + tool_result block).
	if _, ok := result[0]["content"].([]any); !ok {
		t.Errorf("expected array content for mixed merge, got %T", result[0]["content"])
	}
}

func TestThinkFilter_CyrillicPreserved(t *testing.T) {
	// Regression: len(s)-6 splits multibyte UTF-8 (Cyrillic = 2 bytes/rune).
	// Feed text in small chunks so the lookahead path is exercised.
	var out strings.Builder
	f := &thinkFilter{out: func(s string) { out.WriteString(s) }}
	f.feed("Понял")
	f.feed(". Для ")
	f.feed("координации ")
	f.feed("агентов.")
	f.flush()
	want := "Понял. Для координации агентов."
	if out.String() != want {
		t.Errorf("Cyrillic garbled:\n got  %q\n want %q", out.String(), want)
	}
}

func TestThinkFilter_CyrillicWithThinkBlock(t *testing.T) {
	// Cyrillic text around a think block must not lose characters.
	var out strings.Builder
	f := &thinkFilter{out: func(s string) { out.WriteString(s) }}
	f.feed("Привет<think>размышление</think>мир")
	f.flush()
	if out.String() != "Приветмир" {
		t.Errorf("got %q, want %q", out.String(), "Приветмир")
	}
}

// ---------------------------------------------------------------------------
// GetProviderCtx — config-driven context limits
// ---------------------------------------------------------------------------

func TestGetProviderCtx_Defaults(t *testing.T) {
	var rules *RouterRules
	nCtx, charsPerTok, caps := rules.GetProviderCtx("unknown")
	if nCtx != 8192 {
		t.Errorf("default nCtx = %d, want 8192", nCtx)
	}
	if charsPerTok != 4 {
		t.Errorf("default charsPerTok = %d, want 4", charsPerTok)
	}
	if caps["L1"] != 4000 {
		t.Errorf("default L1 cap = %d, want 4000", caps["L1"])
	}
}

func TestGetProviderCtx_FromConfig(t *testing.T) {
	rules := &RouterRules{
		ProviderSettings: map[string]ProviderContextConfig{
			"jan": {
				NCtx:        16384,
				CharsPerTok: 3,
				PrefillCaps: map[string]int{"L1": 2000, "L2": 8000},
			},
		},
	}
	nCtx, charsPerTok, caps := rules.GetProviderCtx("jan")
	if nCtx != 16384 {
		t.Errorf("nCtx = %d, want 16384", nCtx)
	}
	if charsPerTok != 3 {
		t.Errorf("charsPerTok = %d, want 3", charsPerTok)
	}
	if caps["L1"] != 2000 {
		t.Errorf("L1 cap = %d, want 2000", caps["L1"])
	}
}

// ---------------------------------------------------------------------------
// convertToolsToAnthropic
// ---------------------------------------------------------------------------

func TestConvertToolsToAnthropic_Basic(t *testing.T) {
	tools := []Tool{
		{
			Type: "function",
			Function: ToolFunction{
				Name:        "read_file",
				Description: "Read a file from disk",
				Parameters:  []byte(`{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}`),
			},
		},
	}
	result := convertToolsToAnthropic(tools)
	if len(result) != 1 {
		t.Fatalf("expected 1 tool, got %d", len(result))
	}
	if result[0]["name"] != "read_file" {
		t.Errorf("name = %q", result[0]["name"])
	}
	if result[0]["description"] != "Read a file from disk" {
		t.Errorf("description = %q", result[0]["description"])
	}
	schema, ok := result[0]["input_schema"]
	if !ok {
		t.Fatal("input_schema missing")
	}
	// Schema must be non-nil and usable
	schemaMap, ok := schema.(interface{})
	if !ok || schemaMap == nil {
		t.Error("input_schema must be non-nil")
	}
}

func TestConvertToolsToAnthropic_NonFunctionSkipped(t *testing.T) {
	tools := []Tool{
		{Type: "function", Function: ToolFunction{Name: "good"}},
		{Type: "retrieval", Function: ToolFunction{Name: "bad"}},
	}
	result := convertToolsToAnthropic(tools)
	if len(result) != 1 {
		t.Errorf("expected 1 (non-function skipped), got %d", len(result))
	}
	if result[0]["name"] != "good" {
		t.Errorf("expected tool 'good', got %q", result[0]["name"])
	}
}

func TestConvertToolsToAnthropic_EmptyParamsDefaultsToEmptyObject(t *testing.T) {
	tools := []Tool{
		{Type: "function", Function: ToolFunction{Name: "no_params"}},
	}
	result := convertToolsToAnthropic(tools)
	if len(result) != 1 {
		t.Fatalf("expected 1 tool, got %d", len(result))
	}
	if result[0]["input_schema"] == nil {
		t.Error("input_schema must default to empty object, not nil")
	}
}

func TestConvertToolsToAnthropic_MultipleTools(t *testing.T) {
	tools := []Tool{
		{Type: "function", Function: ToolFunction{Name: "tool_a"}},
		{Type: "function", Function: ToolFunction{Name: "tool_b"}},
		{Type: "function", Function: ToolFunction{Name: "tool_c"}},
	}
	result := convertToolsToAnthropic(tools)
	if len(result) != 3 {
		t.Errorf("expected 3 tools, got %d", len(result))
	}
}

// ---------------------------------------------------------------------------
// buildAnthropicMessages — tool_use / tool_result round-trip
// ---------------------------------------------------------------------------

func TestBuildAnthropicMessages_AssistantToolUse(t *testing.T) {
	// OpenAI assistant message with tool_calls → Anthropic structured content
	msgs := []ChatMessage{
		{Role: "user", Content: "what files are here"},
		{
			Role: "assistant",
			ToolCalls: []ToolCall{
				{
					ID:   "tc_1",
					Type: "function",
					Function: ToolCallFunction{Name: "list_dir", Arguments: `{"path":"."}`},
				},
			},
		},
		{Role: "tool", ToolCallID: "tc_1", Content: "file1.go\nfile2.go"},
		{Role: "user", Content: "summarize them"},
	}

	result := buildAnthropicMessages(msgs, 0)

	// Expected Anthropic alternation: user, assistant(tool_use), user(tool_result+text)
	// The last assistant and tool+user get merged into alternating pairs.
	// Verify last message is user and contains a tool_result block.
	if len(result) == 0 {
		t.Fatal("expected at least 1 message")
	}
	last := result[len(result)-1]
	if last["role"] != "user" {
		t.Errorf("last message must be user, got %q", last["role"])
	}

	// Find the assistant message with tool_use
	assistantFound := false
	for _, m := range result {
		if m["role"] == "assistant" {
			if parts, ok := m["content"].([]any); ok {
				for _, p := range parts {
					if part, ok := p.(map[string]any); ok {
						if part["type"] == "tool_use" {
							assistantFound = true
						}
					}
				}
			}
		}
	}
	if !assistantFound {
		t.Error("expected assistant message with tool_use block")
	}
}

func TestBuildAnthropicMessages_EmptyMessages(t *testing.T) {
	result := buildAnthropicMessages([]ChatMessage{}, 0)
	if len(result) != 0 {
		t.Errorf("expected 0 messages, got %d", len(result))
	}
}

func TestBuildAnthropicMessages_SystemOnlyFiltered(t *testing.T) {
	msgs := []ChatMessage{
		{Role: "system", Content: "be helpful"},
	}
	result := buildAnthropicMessages(msgs, 0)
	// System-only input → no messages (no user message to end on)
	if len(result) != 0 {
		t.Errorf("expected 0 messages after filtering system-only, got %d", len(result))
	}
}

func TestGetProviderCtx_ZeroFieldsFallback(t *testing.T) {
	// Zero values in config should fall back to safe defaults
	rules := &RouterRules{
		ProviderSettings: map[string]ProviderContextConfig{
			"jan": {NCtx: 0, CharsPerTok: 0},
		},
	}
	nCtx, charsPerTok, _ := rules.GetProviderCtx("jan")
	if nCtx != 8192 {
		t.Errorf("zero nCtx should default to 8192, got %d", nCtx)
	}
	if charsPerTok != 4 {
		t.Errorf("zero charsPerTok should default to 4, got %d", charsPerTok)
	}
}

// ---------------------------------------------------------------------------
// List models via HTTP test server
// ---------------------------------------------------------------------------

func TestListModelsViaHTTPServer(t *testing.T) {
	srv := setupTestServer(t)

	mux := http.NewServeMux()
	mux.HandleFunc("/v1/models", srv.handleListModels)
	handler := corsMiddleware(mux)

	ts := httptest.NewServer(handler)
	defer ts.Close()

	resp, err := http.Get(ts.URL + "/v1/models")
	if err != nil {
		t.Fatalf("GET /v1/models failed: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		t.Errorf("expected 200, got %d", resp.StatusCode)
	}

	var listResp ListModelsResponse
	if err := json.NewDecoder(resp.Body).Decode(&listResp); err != nil {
		t.Fatalf("failed to decode: %v", err)
	}
	if listResp.Object != "list" {
		t.Errorf("object = %q", listResp.Object)
	}
	// Models may be empty if no backends available; that's fine
	t.Logf("models found: %d", len(listResp.Data))
	for _, m := range listResp.Data {
		t.Logf("  - %s (owned by: %s)", m.ID, m.OwnedBy)
	}
}
