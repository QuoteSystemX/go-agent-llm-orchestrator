package main

import (
	"context"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/mark3labs/mcp-go/mcp"
)

func TestResolveProjectRoot(t *testing.T) {
	root := resolveProjectRoot()
	if root == "" {
		t.Fatal("expected project root to be resolved")
	}
	if _, err := os.Stat(filepath.Join(root, ".agent")); err != nil {
		t.Errorf("project root %q does not contain .agent directory", root)
	}
}

func TestHandlers(t *testing.T) {
	root := resolveProjectRoot()
	h := &handler{projectRoot: root}
	ctx := context.Background()

	t.Run("listSkills", func(t *testing.T) {
		res, err := h.listSkills(ctx, mcp.CallToolRequest{})
		if err != nil {
			t.Errorf("listSkills failed: %v", err)
		}
		if res.IsError {
			t.Errorf("listSkills returned tool error: %v", res.Content)
		}
	})

	t.Run("listSkillsExcludesNonSkillDirs", func(t *testing.T) {
		res, err := h.listSkills(ctx, mcp.CallToolRequest{})
		if err != nil {
			t.Fatalf("listSkills failed: %v", err)
		}
		// res.Content is []interface{} of mcp.TextContent; concatenate their text fields.
		got := map[string]bool{}
		for _, c := range res.Content {
			if tc, ok := c.(mcp.TextContent); ok {
				for line := range strings.SplitSeq(tc.Text, "\n") {
					line = strings.TrimSpace(line)
					if line != "" {
						got[line] = true
					}
				}
			}
		}
		for _, excluded := range []string{"archive", "scratch"} {
			if got[excluded] {
				t.Errorf("listSkills should not contain non-skill dir %q", excluded)
			}
		}
		if !got["clean-code"] {
			t.Errorf("listSkills should contain real skill 'clean-code'")
		}
	})

	t.Run("loadNonSkillDirReturnsError", func(t *testing.T) {
		res, err := h.loadSkill(ctx, mcp.CallToolRequest{Params: mcp.CallToolParams{
			Name:      "archive",
			Arguments: map[string]any{"name": "archive"},
		}})
		if err != nil {
			t.Fatalf("loadSkill returned err: %v", err)
		}
		if res == nil || !res.IsError {
			t.Errorf(`loadSkill("archive") should error (archive/SKILL.md absent), got: %v`, res)
		}
	})

	t.Run("listAgents", func(t *testing.T) {
		res, err := h.listAgents(ctx, mcp.CallToolRequest{})
		if err != nil {
			t.Errorf("listAgents failed: %v", err)
		}
		if res.IsError {
			t.Errorf("listAgents returned tool error: %v", res.Content)
		}
	})

	t.Run("bmadStatus", func(t *testing.T) {
		res, err := h.bmadStatus(ctx, mcp.CallToolRequest{})
		if err != nil {
			t.Errorf("bmadStatus failed: %v", err)
		}
		if res.IsError {
			t.Errorf("bmadStatus returned tool error: %v", res.Content)
		}
	})
}

func TestValidatePath(t *testing.T) {
	root, err := filepath.Abs(".")
	if err != nil {
		t.Fatal(err)
	}
	cases := []struct {
		path    string
		wantErr bool
	}{
		{"safe/path", false},
		{"../../unsafe", true},
		{"/abs/path/with/..", true},
		{filepath.Join(root, "safe/path"), false},
		{"/etc/passwd", true},
	}

	for _, c := range cases {
		err := validatePath(c.path, root)
		if (err != nil) != c.wantErr {
			t.Errorf("validatePath(%q) error = %v, wantErr %v", c.path, err, c.wantErr)
		}
	}
}

// TestLoadAgent_ReturnsConversationStartersVerbatim: the optional nested
// conversation_starters frontmatter key is parsed by consumers (Multica) out
// of agents_load's raw text, so the file must come back byte-for-byte.
func TestLoadAgent_ReturnsConversationStartersVerbatim(t *testing.T) {
	const fixture = `---
name: debugger
description: Debugger.
conversation_starters:
  - label: "Find the root cause: flaky test"
    prompt: |
      TestCheckout fails about once in ten CI runs.
      Find the root cause before anyone retries it again.
---

# Debugger
`
	// validatePath resolves symlinks in the file path but not in the root,
	// and macOS temp dirs live under the /var -> /private/var symlink.
	root, err := filepath.EvalSymlinks(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	agentDir := filepath.Join(root, ".agent", "agents", "qa")
	if err := os.MkdirAll(agentDir, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(agentDir, "debugger.md"), []byte(fixture), 0o644); err != nil {
		t.Fatal(err)
	}

	h := &handler{projectRoot: root}
	req := mcp.CallToolRequest{}
	req.Params.Arguments = map[string]any{"name": "debugger"}
	res, err := h.loadAgent(context.Background(), req)
	if err != nil || res.IsError {
		t.Fatalf("loadAgent failed: err=%v res=%v", err, res)
	}
	tc, ok := res.Content[0].(mcp.TextContent)
	if !ok {
		t.Fatalf("expected text content, got %T", res.Content[0])
	}
	if tc.Text != fixture {
		t.Fatalf("agents_load must return the source file verbatim, got:\n%s", tc.Text)
	}
}
