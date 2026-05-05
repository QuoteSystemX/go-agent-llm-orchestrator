package main

import (
	"context"
	"os"
	"path/filepath"
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
	cases := []struct {
		path    string
		wantErr bool
	}{
		{"safe/path", false},
		{"../../unsafe", true},
		{"/abs/path/with/..", true},
	}

	for _, c := range cases {
		err := validatePath(c.path)
		if (err != nil) != c.wantErr {
			t.Errorf("validatePath(%q) error = %v, wantErr %v", c.path, err, c.wantErr)
		}
	}
}
