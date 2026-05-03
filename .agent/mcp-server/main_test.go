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
	dbPath := filepath.Join(t.TempDir(), "test.db")
	db, err := InitDB(dbPath)
	if err != nil {
		t.Fatalf("failed to init test db: %v", err)
	}
	h := &handler{projectRoot: root, db: db}
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
}

func TestValidatePath(t *testing.T) {
	cases := []struct {
		path    string
		wantErr bool
	}{
		{"safe/path", false},
		{"../../unsafe", true},
		{"/abs/path/with/..", true},
		{"/etc/passwd", true},
		{"/tmp/legit", true},
	}

	for _, c := range cases {
		err := validatePath(c.path)
		if (err != nil) != c.wantErr {
			t.Errorf("validatePath(%q) error = %v, wantErr %v", c.path, err, c.wantErr)
		}
	}
}

func TestLoadItemBoundary(t *testing.T) {
	root := resolveProjectRoot()
	dbPath := filepath.Join(t.TempDir(), "test.db")
	db, _ := InitDB(dbPath)
	h := &handler{projectRoot: root, db: db}

	outsidePath := filepath.Join(root, "..", "..", "etc", "passwd")
	res, err := h.loadItem(outsidePath)
	if err != nil {
		t.Fatalf("loadItem should not return Go error: %v", err)
	}
	if !res.IsError {
		t.Error("expected tool error for path outside project root")
	}
}

func TestSearchSkills(t *testing.T) {
	root := resolveProjectRoot()
	dbPath := filepath.Join(t.TempDir(), "test.db")
	db, _ := InitDB(dbPath)
	h := &handler{projectRoot: root, db: db}
	ctx := context.Background()

	emptyReq := mcp.CallToolRequest{}
	emptyReq.Params.Arguments = map[string]any{"query": ""}
	res, err := h.searchSkills(ctx, emptyReq)
	if err != nil {
		t.Fatalf("searchSkills returned Go error: %v", err)
	}
	if !res.IsError {
		t.Error("expected tool error for empty query")
	}

	validReq := mcp.CallToolRequest{}
	validReq.Params.Arguments = map[string]any{"query": "go"}
	res, err = h.searchSkills(ctx, validReq)
	if err != nil {
		t.Fatalf("searchSkills returned Go error: %v", err)
	}
	if res.IsError {
		t.Errorf("searchSkills unexpected tool error: %v", res.Content)
	}
}
