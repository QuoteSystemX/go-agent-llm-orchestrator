package main

import (
	"context"
	"path/filepath"
	"testing"
	"time"

	"github.com/mark3labs/mcp-go/mcp"
)

func TestRBACEnforcement(t *testing.T) {
	dbPath := filepath.Join(t.TempDir(), "rbac_test.db")
	db, _ := InitDB(dbPath)
	h := &handler{db: db}
	ctx := context.Background()

	toolName := "workflows_list"
	agentName := "untrusted_agent"

	// 1. Initially allowed by default (default policy: allow if no record)
	req := mcp.CallToolRequest{}
	req.Params.Arguments = map[string]any{"_agent": agentName}
	
	// We need to wrap the handler with RBAC to test it
	// In main.go, this is done in main(), so we'll test the helper logic
	withRBAC := func(tool string, hdlr func(context.Context, mcp.CallToolRequest) (*mcp.CallToolResult, error)) func(context.Context, mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
			allowed, _ := h.db.CheckPermission(agentName, tool)
			if !allowed {
				return mcp.NewToolResultError("denied"), nil
			}
			return hdlr(ctx, req)
		}
	}

	rbacHandler := withRBAC(toolName, func(context.Context, mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		return mcp.NewToolResultText("ok"), nil
	})

	res, _ := rbacHandler(ctx, req)
	if res.IsError {
		t.Error("expected access to be allowed by default")
	}

	// 2. Explicitly deny
	h.db.SetPermission(agentName, toolName, false)
	res, _ = rbacHandler(ctx, req)
	if !res.IsError {
		t.Error("expected access to be denied after explicit restriction")
	}
}

func TestCouncilWorkflowBoundaries(t *testing.T) {
	dbPath := filepath.Join(t.TempDir(), "council_test.db")
	db, _ := InitDB(dbPath)
	h := &handler{db: db, projectRoot: "/tmp"}
	ctx := context.Background()

	// Create a proposal that is NOT approved
	pID := "PROP-FAIL"
	h.db.SaveProposal(&CouncilProposal{
		ID:       pID,
		Status:   "open",
		Votes:    1,
		Required: 2,
	})

	req := mcp.CallToolRequest{}
	req.Params.Arguments = map[string]any{"proposal_id": pID}
	
	res, err := h.executeProposal(ctx, req)
	if err != nil {
		t.Fatalf("executeProposal returned Go error: %v", err)
	}
	if !res.IsError {
		t.Error("expected error when executing unapproved proposal")
	}
}

func TestSecretsEdgeCases(t *testing.T) {
	dbPath := filepath.Join(t.TempDir(), "secrets_test.db")
	db, _ := InitDB(dbPath)
	h := &handler{db: db}
	ctx := context.Background()

	// 1. Missing secret
	req := mcp.CallToolRequest{}
	req.Params.Arguments = map[string]any{"key": "nonexistent"}
	res, _ := h.getSecret(ctx, req)
	if !res.IsError {
		t.Error("expected tool error for missing secret")
	}

	// 2. Overwrite secret
	h.db.SetSecret("key1", "val1")
	h.db.SetSecret("key1", "val2")
	val, _ := h.db.GetSecret("key1")
	if val != "val2" {
		t.Errorf("expected val2, got %s", val)
	}
}

func TestMetricsRecording(t *testing.T) {
	dbPath := filepath.Join(t.TempDir(), "metrics_test.db")
	db, _ := InitDB(dbPath)
	h := &handler{db: db}
	
	// Add a dummy metric
	err := h.db.RecordMetric("test_tool", "test_agent", "default", 150*time.Millisecond, true)
	if err != nil {
		t.Fatalf("RecordMetric failed: %v", err)
	}

	ctx := context.Background()
	res, err := h.getMetrics(ctx, mcp.CallToolRequest{})
	if err != nil {
		t.Fatalf("getMetrics failed: %v", err)
	}
	if res.IsError {
		t.Fatalf("getMetrics tool error: %v", res.Content)
	}
}
