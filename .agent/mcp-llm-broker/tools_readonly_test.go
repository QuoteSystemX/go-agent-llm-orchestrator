package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"unicode/utf8"

	"github.com/mark3labs/mcp-go/mcp"
)

// --- Context flags: isLocalOnly / toolsEnabled must be independently settable (AC1) ---

func TestContextFlags_IndependentOfEachOther(t *testing.T) {
	bg := context.Background()

	if isLocalOnly(bg) || toolsEnabled(bg) {
		t.Fatal("plain background context must have neither flag set")
	}

	localOnly := withLocalOnly(bg)
	if !isLocalOnly(localOnly) {
		t.Error("withLocalOnly must set isLocalOnly")
	}
	if toolsEnabled(localOnly) {
		t.Error("withLocalOnly must NOT set toolsEnabled — a plain (non-tool) sub-agent call must be unaffected")
	}

	both := withToolsEnabled(withLocalOnly(bg))
	if !isLocalOnly(both) || !toolsEnabled(both) {
		t.Error("a dispatch must be able to be local-only AND tool-enabled simultaneously")
	}

	toolsOnly := withToolsEnabled(bg)
	if isLocalOnly(toolsOnly) {
		t.Error("withToolsEnabled must not implicitly set isLocalOnly")
	}
	if !toolsEnabled(toolsOnly) {
		t.Error("withToolsEnabled must set toolsEnabled")
	}
}

// --- resolveSandboxedPath: traversal and symlink escape (AC3) ---

func TestResolveSandboxedPath(t *testing.T) {
	root := t.TempDir()
	if err := os.WriteFile(filepath.Join(root, "inside.txt"), []byte("ok"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(filepath.Join(root, "sub"), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(root, "sub", "nested.txt"), []byte("ok"), 0o644); err != nil {
		t.Fatal(err)
	}

	outsideDir := t.TempDir()
	secretOutside := filepath.Join(outsideDir, "secret.txt")
	if err := os.WriteFile(secretOutside, []byte("outside"), 0o644); err != nil {
		t.Fatal(err)
	}

	// Symlink inside the root pointing at a file outside it.
	escapeLink := filepath.Join(root, "escape.txt")
	if err := os.Symlink(secretOutside, escapeLink); err != nil {
		t.Skipf("symlink not supported in this environment: %v", err)
	}

	tests := []struct {
		name    string
		path    string
		wantErr bool
	}{
		{"within root", "inside.txt", false},
		{"nested within root", "sub/nested.txt", false},
		{"dotdot traversal", "../../etc/passwd", true},
		{"dotdot traversal via subdir", "sub/../../outside.txt", true},
		{"absolute path rejected", "/etc/passwd", true},
		{"symlink escape", "escape.txt", true},
		{"empty path", "", true},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			_, err := resolveSandboxedPath(root, tc.path)
			if tc.wantErr && err == nil {
				t.Errorf("resolveSandboxedPath(%q) = nil error, want error", tc.path)
			}
			if !tc.wantErr && err != nil {
				t.Errorf("resolveSandboxedPath(%q) = %v, want nil", tc.path, err)
			}
		})
	}
}

// --- isSecretPath: common secret-bearing globs, case-insensitive (AC4) ---

func TestIsSecretPath(t *testing.T) {
	tests := []struct {
		path string
		want bool
	}{
		{"/repo/.env", true},
		{"/repo/.ENV", true}, // case-insensitive
		{"/repo/.env.production", true},
		{"/repo/id_rsa", true},
		{"/repo/keys/id_ed25519.pub", false}, // .pub is the public half, not secret
		{"/repo/certs/server.pem", true},
		{"/repo/certs/server.PEM", true},
		{"/repo/aws-credentials.json", true},
		{"/repo/main.go", false},
		{"/repo/README.md", false},
		{"/repo/config.yaml", false}, // filename-only refusal — see task card "Scope correction"
	}
	for _, tc := range tests {
		t.Run(tc.path, func(t *testing.T) {
			if got := isSecretPath(tc.path); got != tc.want {
				t.Errorf("isSecretPath(%q) = %v, want %v", tc.path, got, tc.want)
			}
		})
	}
}

// --- readFileTool: whole-file cap, line ranges, secret refusal (AC3, AC4) ---

func TestReadFileTool(t *testing.T) {
	root := t.TempDir()
	small := "line1\nline2\nline3\nline4\nline5\n"
	if err := os.WriteFile(filepath.Join(root, "small.txt"), []byte(small), 0o644); err != nil {
		t.Fatal(err)
	}
	big := strings.Repeat("x", 100)
	if err := os.WriteFile(filepath.Join(root, "big.txt"), []byte(big), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(root, ".env"), []byte("SECRET=1"), 0o644); err != nil {
		t.Fatal(err)
	}

	cfg := SubAgentToolsConfig{MaxBytesPerCall: 50, MaxBytesPerDispatch: 500, MaxToolCalls: 10, MaxGrepMatches: 10}

	t.Run("whole file under cap", func(t *testing.T) {
		budget := newToolBudget(cfg)
		got, err := readFileTool(context.Background(), root, budget, "small.txt", 0, 0)
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if got != small {
			t.Errorf("got %q, want %q", got, small)
		}
	})

	t.Run("whole file over per-call cap without range errors", func(t *testing.T) {
		budget := newToolBudget(cfg)
		_, err := readFileTool(context.Background(), root, budget, "big.txt", 0, 0)
		if err == nil {
			t.Fatal("expected an error for a file larger than the per-call cap with no line range")
		}
		if !strings.Contains(err.Error(), "line range") {
			t.Errorf("error should suggest a line range, got: %v", err)
		}
	})

	t.Run("line range slice", func(t *testing.T) {
		budget := newToolBudget(cfg)
		got, err := readFileTool(context.Background(), root, budget, "small.txt", 2, 3)
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if got != "line2\nline3" {
			t.Errorf("got %q, want %q", got, "line2\nline3")
		}
	})

	t.Run("start_line beyond file length errors", func(t *testing.T) {
		budget := newToolBudget(cfg)
		_, err := readFileTool(context.Background(), root, budget, "small.txt", 999, 1000)
		if err == nil {
			t.Fatal("expected error for out-of-range start_line")
		}
	})

	t.Run("secret file refused", func(t *testing.T) {
		budget := newToolBudget(cfg)
		_, err := readFileTool(context.Background(), root, budget, ".env", 0, 0)
		if err == nil {
			t.Fatal("expected .env to be refused")
		}
	})

	t.Run("nonexistent file errors", func(t *testing.T) {
		budget := newToolBudget(cfg)
		_, err := readFileTool(context.Background(), root, budget, "does-not-exist.txt", 0, 0)
		if err == nil {
			t.Fatal("expected error for nonexistent file")
		}
	})
}

// --- grepTool: matching, secret-file skip, match cap (AC3, AC4) ---

// generousGrepCfg is a shared config literal for grep subtests that don't
// care about budget limits — only "match cap enforced" overrides MaxGrepMatches.
var generousGrepCfg = SubAgentToolsConfig{MaxBytesPerCall: 10000, MaxBytesPerDispatch: 100000, MaxToolCalls: 10, MaxGrepMatches: 10}

func TestGrepTool(t *testing.T) {
	root := t.TempDir()
	if err := os.WriteFile(filepath.Join(root, "a.go"), []byte("func Foo() {}\nfunc Bar() {}\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(root, "id_rsa"), []byte("func Hidden() {}\n"), 0o644); err != nil {
		t.Fatal(err)
	}

	// Regression: real-world repos in this project's own style keep actual
	// source under dot-directories (.agent/, .claude/) — a blanket "skip any
	// dot-prefixed directory" rule (an earlier version of this code had one)
	// would make grep blind to exactly the kind of code a persona is most
	// likely to be asked about. Only VCS/dependency directories are skipped.
	dotDir := filepath.Join(root, ".agent")
	if err := os.MkdirAll(dotDir, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dotDir, "broker.go"), []byte("func LoadRules() {}\n"), 0o644); err != nil {
		t.Fatal(err)
	}

	t.Run("finds a match", func(t *testing.T) {
		budget := newToolBudget(generousGrepCfg)
		got, err := grepTool(context.Background(), root, budget, `func Foo`, "")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if !strings.Contains(got, "a.go") || !strings.Contains(got, "func Foo") {
			t.Errorf("expected a match in a.go, got %q", got)
		}
	})

	t.Run("secret file not searched", func(t *testing.T) {
		budget := newToolBudget(generousGrepCfg)
		got, _ := grepTool(context.Background(), root, budget, `func Hidden`, "")
		if strings.Contains(got, "Hidden") {
			t.Errorf("grep must not search secret-glob files, got %q", got)
		}
	})

	t.Run("descends into project dot-directories", func(t *testing.T) {
		budget := newToolBudget(generousGrepCfg)
		got, err := grepTool(context.Background(), root, budget, `func LoadRules`, "")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if !strings.Contains(got, ".agent/broker.go") && !strings.Contains(got, ".agent"+string(filepath.Separator)+"broker.go") {
			t.Errorf("expected a match inside .agent/, got %q", got)
		}
	})

	t.Run("match cap enforced", func(t *testing.T) {
		cfg := generousGrepCfg
		cfg.MaxGrepMatches = 1
		budget := newToolBudget(cfg)
		got, err := grepTool(context.Background(), root, budget, `func`, "")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if strings.Count(got, "\n")+1 > 1 {
			t.Errorf("expected at most 1 match line, got %q", got)
		}
	})

	t.Run("invalid pattern errors", func(t *testing.T) {
		budget := newToolBudget(generousGrepCfg)
		_, err := grepTool(context.Background(), root, budget, `(unclosed`, "")
		if err == nil {
			t.Fatal("expected error for invalid regex")
		}
	})

	// Regression: a second grep in the same dispatch (same budget) must reuse
	// the cached file walk rather than silently missing a file added between
	// calls — cache is scoped to one toolBudget's lifetime (one dispatch), so
	// within a single grepTool call sequence sharing a budget, results must
	// still be consistent and correct across repeated calls.
	t.Run("repeated calls on same budget stay consistent", func(t *testing.T) {
		budget := newToolBudget(generousGrepCfg)
		first, err := grepTool(context.Background(), root, budget, `func Foo`, "")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		second, err := grepTool(context.Background(), root, budget, `func Foo`, "")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if first != second {
			t.Errorf("expected identical results from cached index, got %q then %q", first, second)
		}
	})
}

// --- toolBudget: call count AND cumulative bytes (AC5) ---

func TestToolBudget_CallCountEnforced(t *testing.T) {
	budget := newToolBudget(SubAgentToolsConfig{MaxToolCalls: 2, MaxBytesPerCall: 1000, MaxBytesPerDispatch: 100000, MaxGrepMatches: 10})
	if err := budget.reserveCall(); err != nil {
		t.Fatalf("call 1 should succeed: %v", err)
	}
	if err := budget.reserveCall(); err != nil {
		t.Fatalf("call 2 should succeed: %v", err)
	}
	if err := budget.reserveCall(); err == nil {
		t.Fatal("call 3 should exceed the budget of 2")
	}
}

// Regression: a call-count-only budget is defeated by chunked line-range
// reads or repeated small reads — the cumulative byte ceiling must be
// enforced independently of the call count (L4 penetration-tester finding).
func TestToolBudget_CumulativeBytesEnforcedAcrossCalls(t *testing.T) {
	budget := newToolBudget(SubAgentToolsConfig{MaxToolCalls: 100, MaxBytesPerCall: 40, MaxBytesPerDispatch: 100, MaxGrepMatches: 10})
	// Three reads of 40 bytes each (each individually within the per-call cap)
	// sum to 120 bytes, exceeding the 100-byte per-dispatch ceiling.
	if err := budget.reserveBytes(40); err != nil {
		t.Fatalf("first 40-byte read should fit: %v", err)
	}
	if err := budget.reserveBytes(40); err != nil {
		t.Fatalf("second 40-byte read should fit (80/100): %v", err)
	}
	if err := budget.reserveBytes(40); err == nil {
		t.Fatal("third 40-byte read should exceed the 100-byte cumulative dispatch budget")
	}
}

// --- getBoolArgDefault ---

func TestGetBoolArgDefault(t *testing.T) {
	b := &BrokerServer{}
	tests := []struct {
		name string
		args interface{}
		def  bool
		want bool
	}{
		{"absent uses default true", map[string]interface{}{}, true, true},
		{"absent uses default false", map[string]interface{}{}, false, false},
		{"native bool true", map[string]interface{}{"tools": true}, false, true},
		{"native bool false", map[string]interface{}{"tools": false}, true, false},
		{"string true", map[string]interface{}{"tools": "true"}, false, true},
		{"string false", map[string]interface{}{"tools": "false"}, true, false},
		{"empty string uses default", map[string]interface{}{"tools": ""}, true, true},
		{"non-map args uses default", "not-a-map", true, true},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			if got := b.getBoolArgDefault(tc.args, "tools", tc.def); got != tc.want {
				t.Errorf("got %v, want %v", got, tc.want)
			}
		})
	}
}

// --- extractToolUsage: handleCallAgent's "verified vs asserted blind" signal (AC6) ---

func TestExtractToolUsage(t *testing.T) {
	t.Run("nil stats", func(t *testing.T) {
		used, calls := extractToolUsage(&ExecutionResult{})
		if used || calls != nil {
			t.Errorf("got used=%v calls=%v, want false/nil", used, calls)
		}
	})

	t.Run("stats without tool_calls key", func(t *testing.T) {
		used, calls := extractToolUsage(&ExecutionResult{Stats: map[string]interface{}{"other": 1}})
		if used || calls != nil {
			t.Errorf("got used=%v calls=%v, want false/nil", used, calls)
		}
	})

	t.Run("empty tool_calls log", func(t *testing.T) {
		used, calls := extractToolUsage(&ExecutionResult{Stats: map[string]interface{}{"tool_calls": []ollamaToolCallRecord{}}})
		if used || calls != nil {
			t.Errorf("empty log must report used_tools=false, got used=%v calls=%v", used, calls)
		}
	})

	t.Run("non-empty tool_calls log", func(t *testing.T) {
		rec := []ollamaToolCallRecord{{Tool: "read_file", Result: "ok"}}
		used, calls := extractToolUsage(&ExecutionResult{Stats: map[string]interface{}{"tool_calls": rec}})
		if !used || len(calls) != 1 {
			t.Errorf("got used=%v calls=%v, want true/[1 item]", used, calls)
		}
	})
}

// --- executeOllamaToolLoop: wire format + multi-turn (AC2, AC7) ---

func TestExecuteOllamaToolLoop_ToolThenAnswer(t *testing.T) {
	root := t.TempDir()
	if err := os.WriteFile(filepath.Join(root, "issue.go"), []byte("package model\n\ntype Issue struct{}\n"), 0o644); err != nil {
		t.Fatal(err)
	}

	var callCount int
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		callCount++
		w.Header().Set("Content-Type", "application/json")
		if callCount == 1 {
			// First turn: model calls read_file — matches the shape verified
			// empirically against oamazonasgabriel/qwen3.6-35b-a3b:q4-24gbGPU.
			_, _ = w.Write([]byte(`{
				"message": {
					"role": "assistant",
					"content": "",
					"tool_calls": [{"id":"call_1","function":{"name":"read_file","arguments":{"path":"issue.go"}}}]
				},
				"done": true
			}`))
			return
		}
		// Second turn: model has the tool result (a role:"tool" message should
		// be present) and synthesizes a final answer with no further tool_calls.
		var body map[string]any
		_ = json.NewDecoder(r.Body).Decode(&body)
		msgs, _ := body["messages"].([]any)
		sawToolResult := false
		for _, m := range msgs {
			if mm, ok := m.(map[string]any); ok && mm["role"] == "tool" {
				sawToolResult = true
			}
		}
		if !sawToolResult {
			http.Error(w, "expected a role:tool message in the follow-up request", http.StatusBadRequest)
			return
		}
		_, _ = w.Write([]byte(`{"message": {"role": "assistant", "content": "issue.go defines type Issue."}, "done": true}`))
	}))
	defer server.Close()

	b := &BrokerServer{workspaceRoot: root}
	resp, log, err := b.executeOllamaToolLoop(context.Background(), "Does issue.go define type Issue?", "", "test-model", server.URL, 0, nil)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if resp != "issue.go defines type Issue." {
		t.Errorf("got response %q", resp)
	}
	if len(log) != 1 || log[0].Tool != "read_file" || log[0].Error != "" {
		t.Errorf("expected one successful read_file record, got %+v", log)
	}
	if callCount != 2 {
		t.Errorf("expected exactly 2 HTTP calls (tool turn + synthesis turn), got %d", callCount)
	}
}

func TestExecuteOllamaToolLoop_NoToolCallReturnsDirectly(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"message": {"role": "assistant", "content": "no tool needed"}, "done": true}`))
	}))
	defer server.Close()

	b := &BrokerServer{workspaceRoot: t.TempDir()}
	resp, log, err := b.executeOllamaToolLoop(context.Background(), "hi", "", "test-model", server.URL, 0, nil)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if resp != "no tool needed" {
		t.Errorf("got %q", resp)
	}
	if len(log) != 0 {
		t.Errorf("expected no tool calls logged, got %+v", log)
	}
}

// Regression: the per-dispatch budget must actually stop the loop, not just
// be recorded — a model that keeps requesting tools past the budget must be
// told plainly and forced toward a final answer rather than looping forever.
func TestExecuteOllamaToolLoop_BudgetExhaustionStopsToolExecution(t *testing.T) {
	root := t.TempDir()
	for i := 0; i < 10; i++ {
		name := "f" + string(rune('a'+i)) + ".txt"
		if err := os.WriteFile(filepath.Join(root, name), []byte("x"), 0o644); err != nil {
			t.Fatal(err)
		}
	}

	var callCount int
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		callCount++
		w.Header().Set("Content-Type", "application/json")
		if callCount > 6 {
			// Should not be reached: MaxIterations caps this well before.
			_, _ = w.Write([]byte(`{"message":{"role":"assistant","content":"stop"},"done":true}`))
			return
		}
		_, _ = w.Write([]byte(`{
			"message": {
				"role": "assistant", "content": "",
				"tool_calls": [{"id":"call_x","function":{"name":"read_file","arguments":{"path":"fa.txt"}}}]
			},
			"done": true
		}`))
	}))
	defer server.Close()

	b := &BrokerServer{workspaceRoot: root}
	// MaxToolCalls: 2 — the loop must stop granting tool results well before
	// the model's iteration count runs away.
	_ = SubAgentToolsConfig{} // documents: rules.SubAgentTools left zero -> defaults apply (5 calls / 6 iterations)
	_, log, err := b.executeOllamaToolLoop(context.Background(), "verify things", "", "test-model", server.URL, 0, nil)
	if err == nil {
		t.Fatal("expected an error: the model never produces a final answer in this test")
	}
	if callCount > ToolLoopDefaultMaxIterations {
		t.Errorf("loop made %d HTTP calls, exceeding MaxIterations=%d", callCount, ToolLoopDefaultMaxIterations)
	}
	successCount := 0
	for _, rec := range log {
		if rec.Error == "" {
			successCount++
		}
	}
	if successCount > ToolLoopDefaultMaxCalls {
		t.Errorf("%d tool calls succeeded, exceeding the per-dispatch budget of %d", successCount, ToolLoopDefaultMaxCalls)
	}
}

// --- End-to-end: handleCallAgent through the real dispatch/routing path (AC1, AC6, AC7) ---

func TestHandleCallAgent_EndToEnd_UsesToolsAndSurfacesUsage(t *testing.T) {
	root := t.TempDir()

	agentsDir := filepath.Join(root, ".agent", "agents", "domain")
	if err := os.MkdirAll(agentsDir, 0o755); err != nil {
		t.Fatal(err)
	}
	agentMd := "---\nname: test-persona\ndescription: test persona\n---\nYou are a careful test persona. Verify claims with tools before answering.\n"
	if err := os.WriteFile(filepath.Join(agentsDir, "test-persona.md"), []byte(agentMd), 0o644); err != nil {
		t.Fatal(err)
	}

	if err := os.WriteFile(filepath.Join(root, "issue.go"), []byte("package model\n\ntype Issue struct{}\n"), 0o644); err != nil {
		t.Fatal(err)
	}

	cfgDir := filepath.Join(root, ".agent", "config")
	if err := os.MkdirAll(cfgDir, 0o755); err != nil {
		t.Fatal(err)
	}
	rules := `{
		"models": {"ollama": {"L1": "test-model"}},
		"hybrid_routing": {"cloud_fallback_provider": "antigravity", "cloud_on_tiers": []}
	}`
	if err := os.WriteFile(filepath.Join(cfgDir, "router_rules.json"), []byte(rules), 0o644); err != nil {
		t.Fatal(err)
	}

	var chatCalls int
	mock := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch {
		case strings.HasSuffix(r.URL.Path, "/api/tags"):
			_, _ = w.Write([]byte(`{"models":[{"name":"test-model"}]}`))
		case strings.HasSuffix(r.URL.Path, "/api/chat"):
			chatCalls++
			if chatCalls == 1 {
				_, _ = w.Write([]byte(`{
					"message": {"role":"assistant","content":"","tool_calls":[{"id":"c1","function":{"name":"read_file","arguments":{"path":"issue.go"}}}]},
					"done": true
				}`))
				return
			}
			_, _ = w.Write([]byte(`{"message": {"role":"assistant","content":"issue.go defines type Issue, verified."}, "done": true}`))
		default:
			http.Error(w, "unexpected path "+r.URL.Path, http.StatusNotFound)
		}
	}))
	defer mock.Close()

	oldHost := os.Getenv("OLLAMA_HOST")
	_ = os.Setenv("OLLAMA_HOST", mock.URL)
	defer os.Setenv("OLLAMA_HOST", oldHost)

	srv := &BrokerServer{
		workspaceRoot: root,
		healthCache:   map[string]BackendHealth{"ollama": {Available: true}},
	}

	req := mcp.CallToolRequest{
		Request: mcp.Request{Method: "tools/call"},
		Params: mcp.CallToolParams{
			Name: "call_agent",
			Arguments: map[string]any{
				"agent_name": "test-persona",
				"task":       "Does issue.go define type Issue?",
				"tier":       "L1",
			},
		},
	}

	res, err := srv.handleCallAgent(context.Background(), req)
	if err != nil {
		t.Fatalf("handleCallAgent failed: %v", err)
	}
	if res.IsError {
		var msg string
		for _, c := range res.Content {
			if txt, ok := c.(mcp.TextContent); ok {
				msg += txt.Text
			}
		}
		t.Fatalf("handleCallAgent returned an error result: %s", msg)
	}

	var text string
	for _, c := range res.Content {
		if txt, ok := c.(mcp.TextContent); ok {
			text = txt.Text
		}
	}

	var parsed struct {
		Response  string                 `json:"response"`
		Provider  string                 `json:"provider"`
		UsedTools bool                   `json:"used_tools"`
		ToolCalls []ollamaToolCallRecord `json:"tool_calls"`
	}
	if err := json.Unmarshal([]byte(text), &parsed); err != nil {
		t.Fatalf("failed to parse handleCallAgent response: %v\nraw: %s", err, text)
	}

	if parsed.Provider != ProviderOllama {
		t.Errorf("expected provider %q, got %q", ProviderOllama, parsed.Provider)
	}
	if !parsed.UsedTools {
		t.Error("expected used_tools=true — the persona called read_file")
	}
	if len(parsed.ToolCalls) != 1 || parsed.ToolCalls[0].Tool != "read_file" {
		t.Errorf("expected one read_file tool_calls entry, got %+v", parsed.ToolCalls)
	}
	if !strings.Contains(parsed.Response, "verified") {
		t.Errorf("expected the synthesized answer to come through, got %q", parsed.Response)
	}
}

// Companion to the above: a plain (tools:"false") sub-agent call must behave
// exactly like the pre-existing buffered path — no /api/chat call, no
// tool_calls in the response (AC1's "unaffected" requirement).
func TestHandleCallAgent_ToolsDisabled_UsesBufferedPathUnaffected(t *testing.T) {
	root := t.TempDir()
	agentsDir := filepath.Join(root, ".agent", "agents", "domain")
	if err := os.MkdirAll(agentsDir, 0o755); err != nil {
		t.Fatal(err)
	}
	agentMd := "---\nname: test-persona\ndescription: test persona\n---\nYou are a test persona.\n"
	if err := os.WriteFile(filepath.Join(agentsDir, "test-persona.md"), []byte(agentMd), 0o644); err != nil {
		t.Fatal(err)
	}
	cfgDir := filepath.Join(root, ".agent", "config")
	if err := os.MkdirAll(cfgDir, 0o755); err != nil {
		t.Fatal(err)
	}
	rules := `{
		"models": {"ollama": {"L1": "test-model"}},
		"hybrid_routing": {"cloud_fallback_provider": "antigravity", "cloud_on_tiers": []}
	}`
	if err := os.WriteFile(filepath.Join(cfgDir, "router_rules.json"), []byte(rules), 0o644); err != nil {
		t.Fatal(err)
	}

	var sawChatEndpoint bool
	mock := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch {
		case strings.HasSuffix(r.URL.Path, "/api/tags"):
			_, _ = w.Write([]byte(`{"models":[{"name":"test-model"}]}`))
		case strings.HasSuffix(r.URL.Path, "/api/chat"):
			sawChatEndpoint = true
			http.Error(w, "must not be called when tools are disabled", http.StatusBadRequest)
		case strings.HasSuffix(r.URL.Path, "/api/generate"):
			_, _ = w.Write([]byte(`{"response": "plain answer", "eval_count": 3}`))
		default:
			http.Error(w, "unexpected path "+r.URL.Path, http.StatusNotFound)
		}
	}))
	defer mock.Close()

	oldHost := os.Getenv("OLLAMA_HOST")
	_ = os.Setenv("OLLAMA_HOST", mock.URL)
	defer os.Setenv("OLLAMA_HOST", oldHost)

	srv := &BrokerServer{
		workspaceRoot: root,
		healthCache:   map[string]BackendHealth{"ollama": {Available: true}},
	}

	req := mcp.CallToolRequest{
		Request: mcp.Request{Method: "tools/call"},
		Params: mcp.CallToolParams{
			Name: "call_agent",
			Arguments: map[string]any{
				"agent_name": "test-persona",
				"task":       "Say hello",
				"tier":       "L1",
				"tools":      "false",
			},
		},
	}

	res, err := srv.handleCallAgent(context.Background(), req)
	if err != nil {
		t.Fatalf("handleCallAgent failed: %v", err)
	}
	if res.IsError {
		var msg string
		for _, c := range res.Content {
			if txt, ok := c.(mcp.TextContent); ok {
				msg += txt.Text
			}
		}
		t.Fatalf("handleCallAgent returned an error result: %s", msg)
	}
	if sawChatEndpoint {
		t.Error("tools:\"false\" must never hit /api/chat")
	}

	var text string
	for _, c := range res.Content {
		if txt, ok := c.(mcp.TextContent); ok {
			text = txt.Text
		}
	}
	var parsed struct {
		Response  string `json:"response"`
		UsedTools bool   `json:"used_tools"`
	}
	if err := json.Unmarshal([]byte(text), &parsed); err != nil {
		t.Fatalf("failed to parse response: %v\nraw: %s", err, text)
	}
	if parsed.UsedTools {
		t.Error("used_tools must be false when tools were disabled for this dispatch")
	}
	if parsed.Response != "plain answer" {
		t.Errorf("expected the plain buffered-path response, got %q", parsed.Response)
	}
}

// --- truncateAtRuneBoundary: must never split a multi-byte UTF-8 rune ---

func TestTruncateAtRuneBoundary(t *testing.T) {
	tests := []struct {
		name     string
		input    string
		maxBytes int
	}{
		{"ascii under limit unchanged", "hello", 100},
		{"ascii exact cut", "hello world", 5},
		{"cyrillic near boundary", strings.Repeat("проверка ", 20), 37}, // odd byte count lands mid-rune naively
		{"emoji near boundary", strings.Repeat("🤖📎⚠️", 10), 13},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got := truncateAtRuneBoundary(tc.input, tc.maxBytes)
			if len(got) > tc.maxBytes {
				t.Errorf("result is %d bytes, exceeds maxBytes=%d", len(got), tc.maxBytes)
			}
			if !utf8.ValidString(got) {
				t.Errorf("result is not valid UTF-8: %q (bytes: %v)", got, []byte(got))
			}
		})
	}
}

// --- coerceIntArg: accept both native JSON numbers and numeric strings ---

func TestCoerceIntArg(t *testing.T) {
	tests := []struct {
		name string
		args map[string]any
		want int
	}{
		{"native float64", map[string]any{"start_line": float64(42)}, 42},
		{"numeric string", map[string]any{"start_line": "42"}, 42},
		{"numeric string with whitespace", map[string]any{"start_line": " 42 "}, 42},
		{"absent", map[string]any{}, 0},
		{"non-numeric string", map[string]any{"start_line": "not-a-number"}, 0},
		{"wrong type", map[string]any{"start_line": true}, 0},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			if got := coerceIntArg(tc.args, "start_line"); got != tc.want {
				t.Errorf("got %d, want %d", got, tc.want)
			}
		})
	}
}

// Regression: a model that sends start_line/end_line as JSON strings (a real
// quirk, same class as the arguments-object string-fallback already handled
// in executeOllamaToolLoop) must not silently fall back to "no range given".
func TestRunReadOnlyTool_ReadFile_AcceptsStringLineNumbers(t *testing.T) {
	root := t.TempDir()
	content := "line1\nline2\nline3\nline4\nline5\n"
	if err := os.WriteFile(filepath.Join(root, "f.txt"), []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
	b := &BrokerServer{workspaceRoot: root}
	budget := newToolBudget(SubAgentToolsConfig{MaxBytesPerCall: 10000, MaxBytesPerDispatch: 100000, MaxToolCalls: 10, MaxGrepMatches: 10})

	got, err := b.runReadOnlyTool(context.Background(), "read_file", map[string]any{
		"path":       "f.txt",
		"start_line": "2",
		"end_line":   "3",
	}, budget)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != "line2\nline3" {
		t.Errorf("got %q, want %q", got, "line2\nline3")
	}
}

// Regression: line-range reads must stream rather than load the whole file —
// verified indirectly by confirming a large file (over MaxBytesPerCall) that
// would fail the whole-file path succeeds when a narrow line range is given.
func TestReadFileTool_LineRangeOnLargeFileSucceeds(t *testing.T) {
	root := t.TempDir()
	var sb strings.Builder
	for i := 1; i <= 5000; i++ {
		fmt.Fprintf(&sb, "line number %d filler filler filler\n", i)
	}
	if err := os.WriteFile(filepath.Join(root, "large.txt"), []byte(sb.String()), 0o644); err != nil {
		t.Fatal(err)
	}
	budget := newToolBudget(SubAgentToolsConfig{MaxBytesPerCall: 200, MaxBytesPerDispatch: 100000, MaxToolCalls: 10, MaxGrepMatches: 10})

	got, err := readFileTool(context.Background(), root, budget, "large.txt", 4990, 4991)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !strings.Contains(got, "line number 4990") || !strings.Contains(got, "line number 4991") {
		t.Errorf("expected lines 4990-4991, got %q", got)
	}
}
