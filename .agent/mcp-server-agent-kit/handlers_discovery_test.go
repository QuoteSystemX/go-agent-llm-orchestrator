package main

import (
	"context"
	"encoding/json"
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

// starterAgentFixture carries the optional conversation_starters frontmatter
// key (nested list, block-scalar prompts, quoted label with a colon).
// Consumers such as Multica parse it out of agents_load's raw text, so the
// server must hand the file back byte-for-byte.
const starterAgentFixture = `---
name: backend-lead
description: Backend Engineering Lead.
conversation_starters:
  - label: "Plan the sprint: backend"
    prompt: |
      Review the open backend tasks and propose an order.
      Group them by service: api, worker.
  - label: Triage failing jobs
    prompt: >
      Look at the jobs that failed overnight
      and tell me who should own each one.
skills: clean-code
---

# Backend Lead
`

func writeStarterAgent(t *testing.T) string {
	t.Helper()
	root := t.TempDir()
	agentDir := filepath.Join(root, ".agent", "agents", "management")
	if err := os.MkdirAll(agentDir, 0o755); err != nil {
		t.Fatalf("failed to create agent dir: %v", err)
	}
	if err := os.WriteFile(filepath.Join(agentDir, "backend-lead.md"), []byte(starterAgentFixture), 0o644); err != nil {
		t.Fatalf("failed to write agent file: %v", err)
	}
	return root
}

func TestLoadAgent_ReturnsConversationStartersVerbatim(t *testing.T) {
	h := &handler{projectRoot: writeStarterAgent(t)}
	req := mcp.CallToolRequest{}
	req.Params.Arguments = map[string]any{"name": "backend-lead"}

	res, err := h.loadAgent(context.Background(), req)
	if err != nil || res.IsError {
		t.Fatalf("loadAgent failed: err=%v res=%v", err, res)
	}
	tc, ok := res.Content[0].(mcp.TextContent)
	if !ok {
		t.Fatalf("expected text content, got %T", res.Content[0])
	}
	if tc.Text != starterAgentFixture {
		t.Fatalf("agents_load must return the source file verbatim, got:\n%s", tc.Text)
	}
}

// TestListAgents_IgnoresConversationStartersLines guards the flat line-based
// parseFrontmatter: starter lines must not leak into name/description.
func TestListAgents_IgnoresConversationStartersLines(t *testing.T) {
	h := &handler{projectRoot: writeStarterAgent(t)}

	res, err := h.listAgents(context.Background(), mcp.CallToolRequest{})
	if err != nil || res.IsError {
		t.Fatalf("listAgents failed: err=%v res=%v", err, res)
	}
	var infos []RegistryInfo
	if err := json.Unmarshal([]byte(res.Content[0].(mcp.TextContent).Text), &infos); err != nil {
		t.Fatalf("listAgents returned invalid JSON: %v", err)
	}
	if len(infos) != 1 || infos[0].Name != "backend-lead" || infos[0].Description != "Backend Engineering Lead." {
		t.Fatalf("unexpected listAgents result: %+v", infos)
	}
}
