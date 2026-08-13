package main

import (
	"context"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/mark3labs/mcp-go/mcp"
)

const testLessonsFixture = `# Global Lessons Learned

## Memory leak in worker pool
Score high on memory/leak: a goroutine leak in the worker pool caused
memory to grow unbounded under sustained load. Fixed by closing the done
channel on shutdown.

## Slow database query on issue list
The issue list endpoint was slow because of a missing index on
workspace_id. Added a composite index, query time dropped from 900ms to 12ms.

### Auth token race condition
A race condition in token refresh caused intermittent 401s under
concurrent auth token requests. Fixed with a singleflight guard.
`

// writeTestLessonsFixture creates a temp global-knowledge root with a
// lessons_learned.md fixture and points AGENT_GLOBAL_ROOT at it — the same
// env var lib/paths.py's GLOBAL_LESSONS_PATH respects, so this exercises
// the exact resolution path production uses.
func writeTestLessonsFixture(t *testing.T, content string) {
	t.Helper()
	root := t.TempDir()
	if err := os.WriteFile(filepath.Join(root, "lessons_learned.md"), []byte(content), 0o644); err != nil {
		t.Fatalf("failed to write lessons fixture: %v", err)
	}
	t.Setenv("AGENT_GLOBAL_ROOT", root)
}

// TestSearchKnowledge_ReturnsRealResults is the regression test for
// tasks/done/2026-08-12-agent-kit-search-knowledge-broken.md: search_knowledge
// must return real, scored results for a matching query using embedded Go
// logic — no python3 subprocess, no "executable file not found in $PATH".
func TestSearchKnowledge_ReturnsRealResults(t *testing.T) {
	writeTestLessonsFixture(t, testLessonsFixture)

	h := &handler{projectRoot: t.TempDir()}
	req := mcp.CallToolRequest{}
	req.Params.Arguments = map[string]any{"query": "memory leak"}

	res, err := h.searchKnowledge(context.Background(), req)
	if err != nil {
		t.Fatalf("searchKnowledge returned unexpected error: %v", err)
	}
	if res.IsError {
		t.Fatalf("expected a successful result, got tool error: %v", res.Content)
	}
	text, ok := res.Content[0].(mcp.TextContent)
	if !ok {
		t.Fatalf("expected TextContent, got %T", res.Content[0])
	}
	if !strings.Contains(text.Text, "Memory leak in worker pool") {
		t.Errorf("expected the matching lesson section in the result, got: %s", text.Text)
	}
	if strings.Contains(text.Text, "No relevant lessons found") {
		t.Errorf("expected real matches, not the no-match fallback, got: %s", text.Text)
	}
}

// TestSearchKnowledge_ShortMatch_NoFalseTruncationMarker is the regression
// test for a code-review finding on this same fix: a lesson section under
// the 300-rune truncation threshold must not get a trailing "..." appended
// — that falsely signals the content was cut off when it's actually
// complete.
func TestSearchKnowledge_ShortMatch_NoFalseTruncationMarker(t *testing.T) {
	writeTestLessonsFixture(t, testLessonsFixture)

	h := &handler{projectRoot: t.TempDir()}
	req := mcp.CallToolRequest{}
	req.Params.Arguments = map[string]any{"query": "auth token race"}

	res, err := h.searchKnowledge(context.Background(), req)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	text := res.Content[0].(mcp.TextContent).Text
	if strings.HasSuffix(strings.TrimRight(text, "\n"), "...") {
		t.Errorf("short (untruncated) match must not end with a false truncation marker, got: %s", text)
	}
}

// TestSearchKnowledge_RanksBestMatchFirst locks in score-descending
// ordering — a Go port of semantic_brain_engine.py's weighted Jaccard-like
// scoring, ranked by relevance rather than file order.
func TestSearchKnowledge_RanksBestMatchFirst(t *testing.T) {
	writeTestLessonsFixture(t, testLessonsFixture)

	matches := searchGlobalLessons("auth token race", 5)
	if len(matches) == 0 {
		t.Fatal("expected at least one match")
	}
	if !strings.Contains(matches[0].Content, "Auth token race condition") {
		t.Errorf("expected the auth/token/race section to rank first, got top match: %s", matches[0].Content)
	}
	for i := 1; i < len(matches); i++ {
		if matches[i].Score > matches[i-1].Score {
			t.Errorf("results not sorted score-descending: index %d (%.2f) > index %d (%.2f)", i, matches[i].Score, i-1, matches[i-1].Score)
		}
	}
}

// TestSearchKnowledge_NoMatch_ReturnsFriendlyEmptyResult covers a query with
// no keyword overlap — must degrade to the "no relevant lessons" message,
// not an error and not a crash.
func TestSearchKnowledge_NoMatch_ReturnsFriendlyEmptyResult(t *testing.T) {
	writeTestLessonsFixture(t, testLessonsFixture)

	h := &handler{projectRoot: t.TempDir()}
	req := mcp.CallToolRequest{}
	req.Params.Arguments = map[string]any{"query": "zzzznonexistentzzzz"}

	res, err := h.searchKnowledge(context.Background(), req)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if res.IsError {
		t.Fatalf("a no-match query must not be a tool error, got: %v", res.Content)
	}
	text := res.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "No relevant lessons found") {
		t.Errorf("expected the no-match fallback message, got: %s", text)
	}
}

// TestSearchKnowledge_MissingLessonsFile_DoesNotError covers the case where
// the global knowledge base was never initialized on this host — must
// degrade gracefully, matching semantic_brain_engine.py's
// GLOBAL_LESSONS_PATH.exists() early return.
func TestSearchKnowledge_MissingLessonsFile_DoesNotError(t *testing.T) {
	t.Setenv("AGENT_GLOBAL_ROOT", t.TempDir()) // empty dir, no lessons_learned.md

	h := &handler{projectRoot: t.TempDir()}
	req := mcp.CallToolRequest{}
	req.Params.Arguments = map[string]any{"query": "anything"}

	res, err := h.searchKnowledge(context.Background(), req)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if res.IsError {
		t.Fatalf("a missing lessons file must not be a tool error, got: %v", res.Content)
	}
}

// TestSplitLessonSections_MatchesPythonLookaheadSplit locks in behavioral
// parity with semantic_brain_engine.py's re.split(r'\n(?=##|###)', content):
// a new section starts at any line beginning with "##"/"###"; the leading
// preamble before the first heading is its own section; a "#"-only (h1)
// line does not split.
func TestSplitLessonSections_MatchesPythonLookaheadSplit(t *testing.T) {
	content := "preamble\ntext\n## Section One\nbody one\n### Section Two\nbody two\n# Not a split point\nstill section two"
	sections := splitLessonSections(content)
	if len(sections) != 3 {
		t.Fatalf("expected 3 sections, got %d: %#v", len(sections), sections)
	}
	if sections[0] != "preamble\ntext" {
		t.Errorf("expected preamble section, got: %q", sections[0])
	}
	if !strings.Contains(sections[1], "Section One") || strings.Contains(sections[1], "Section Two") {
		t.Errorf("expected section 1 to contain only 'Section One', got: %q", sections[1])
	}
	if !strings.Contains(sections[2], "Section Two") || !strings.Contains(sections[2], "Not a split point") {
		t.Errorf("expected section 2 to absorb the h1 line (no split on single '#'), got: %q", sections[2])
	}
}

// TestPreprocessTokens_DedupesAndStripsPunctuation locks in parity with
// semantic_brain_engine.py's preprocess(): lowercase, strip non-alnum
// (keeping whitespace), split, dedupe.
func TestPreprocessTokens_DedupesAndStripsPunctuation(t *testing.T) {
	tokens := preprocessTokens("Memory, memory! Leak-detection (API).")
	counts := make(map[string]int)
	for _, tok := range tokens {
		counts[tok]++
	}
	if counts["memory"] != 1 {
		t.Errorf("expected 'memory' deduped to a single token, got count=%d in %v", counts["memory"], tokens)
	}
	if counts["leakdetection"] != 1 {
		t.Errorf("expected punctuation stripped ('leak-detection' -> 'leakdetection'), got tokens: %v", tokens)
	}
	if counts["api"] != 1 {
		t.Errorf("expected 'api' token present, got: %v", tokens)
	}
}
