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
