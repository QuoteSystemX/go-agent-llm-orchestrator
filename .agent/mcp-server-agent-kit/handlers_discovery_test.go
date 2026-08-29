package main

import (
	"context"
	"os"
	"path/filepath"
	"testing"

	"github.com/mark3labs/mcp-go/mcp"
)

// TestLoadAgent_MissingAgentsRoot guards against a nil pointer dereference in
// loadAgent's filepath.WalkDir callback. When projectRoot has no .agent/agents
// directory, WalkDir invokes the callback once with a non-nil err and a nil
// fs.DirEntry; the old code ignored err and dereferenced the nil DirEntry
// directly, panicking. In production this panic escaped net/http's
// per-connection recovery as a closed connection with no response body,
// which MCP clients surfaced as a bare transport EOF instead of a normal
// tool error.
func TestLoadAgent_MissingAgentsRoot(t *testing.T) {
	h := &handler{projectRoot: t.TempDir()}
	ctx := context.Background()

	req := mcp.CallToolRequest{}
	req.Params.Arguments = map[string]any{"name": "orchestrator"}

	res, err := h.loadAgent(ctx, req)
	if err != nil {
		t.Fatalf("loadAgent returned unexpected error: %v", err)
	}
	if !res.IsError {
		t.Fatal("expected a tool error result for a missing agents root, got success")
	}
}

// TestLoadAgent_FindsAgentInSubfolder covers the happy path: loadAgent must
// still recurse into category subfolders under .agent/agents to find the file.
func TestLoadAgent_FindsAgentInSubfolder(t *testing.T) {
	root := t.TempDir()
	agentDir := filepath.Join(root, ".agent", "agents", "core")
	if err := os.MkdirAll(agentDir, 0o755); err != nil {
		t.Fatalf("failed to create agent dir: %v", err)
	}
	agentFile := filepath.Join(agentDir, "orchestrator.md")
	if err := os.WriteFile(agentFile, []byte("# Orchestrator\n"), 0o644); err != nil {
		t.Fatalf("failed to write agent file: %v", err)
	}

	h := &handler{projectRoot: root}
	ctx := context.Background()

	req := mcp.CallToolRequest{}
	req.Params.Arguments = map[string]any{"name": "orchestrator"}

	res, err := h.loadAgent(ctx, req)
	if err != nil {
		t.Fatalf("loadAgent returned unexpected error: %v", err)
	}
	if res.IsError {
		t.Fatalf("expected success loading existing agent, got error result")
	}
}

// TestLoadAgent_FallsBackToPrettyName covers the bug reported 2026-08-13:
// listAgents returns both an ID (the real filename) and a Name (frontmatter
// `name:`, or a Title-Cased fallback derived from the ID - see
// resolveDirName's doc comment). A caller passing that Name back into
// loadAgent used to fail: sanitizeString only strips characters, it doesn't
// normalize spacing/case, so "Prompt Red Teamer" became
// "PromptRedTeamer.md", matching nothing. loadAgent must also try the
// slugified form.
func TestLoadAgent_FallsBackToPrettyName(t *testing.T) {
	root := t.TempDir()
	agentDir := filepath.Join(root, ".agent", "agents", "qa")
	if err := os.MkdirAll(agentDir, 0o755); err != nil {
		t.Fatalf("failed to create agent dir: %v", err)
	}
	agentFile := filepath.Join(agentDir, "prompt-red-teamer.md")
	if err := os.WriteFile(agentFile, []byte("# Prompt Red Teamer\n"), 0o644); err != nil {
		t.Fatalf("failed to write agent file: %v", err)
	}

	h := &handler{projectRoot: root}
	ctx := context.Background()

	req := mcp.CallToolRequest{}
	req.Params.Arguments = map[string]any{"name": "Prompt Red Teamer"}

	res, err := h.loadAgent(ctx, req)
	if err != nil {
		t.Fatalf("loadAgent returned unexpected error: %v", err)
	}
	if res.IsError {
		t.Fatalf("expected success loading agent via pretty display name, got error result")
	}
}

// TestLoadSkill_FallsBackToPrettyName is the skill-side counterpart to
// TestLoadAgent_FallsBackToPrettyName, covering loadSkill via resolveDirName.
func TestLoadSkill_FallsBackToPrettyName(t *testing.T) {
	root := t.TempDir()
	skillDir := filepath.Join(root, ".agent", "skills", "adversarial-prompt-testing")
	if err := os.MkdirAll(skillDir, 0o755); err != nil {
		t.Fatalf("failed to create skill dir: %v", err)
	}
	skillFile := filepath.Join(skillDir, "SKILL.md")
	if err := os.WriteFile(skillFile, []byte("---\nname: adversarial-prompt-testing\n---\n"), 0o644); err != nil {
		t.Fatalf("failed to write SKILL.md: %v", err)
	}

	h := &handler{projectRoot: root}
	ctx := context.Background()

	req := mcp.CallToolRequest{}
	req.Params.Arguments = map[string]any{"name": "Adversarial Prompt Testing"}

	res, err := h.loadSkill(ctx, req)
	if err != nil {
		t.Fatalf("loadSkill returned unexpected error: %v", err)
	}
	if res.IsError {
		t.Fatalf("expected success loading skill via pretty display name, got error result")
	}
}
