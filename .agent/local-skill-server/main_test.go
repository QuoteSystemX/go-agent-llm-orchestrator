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
				for _, line := range strings.Split(tc.Text, "\n") {
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
