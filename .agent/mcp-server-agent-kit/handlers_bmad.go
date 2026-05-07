package main

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/mark3labs/mcp-go/mcp"
)

func (h *handler) decomposePRD(_ context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	prdPath, _ := req.RequireString("prd_path")
	
	scriptPath := filepath.Join(h.projectRoot, ".agent", "scripts", "prd_decomposer.py")
	cmd := exec.Command("python3", scriptPath, prdPath)
	cmd.Dir = h.projectRoot
	output, err := cmd.CombinedOutput()
	
	if err != nil {
		return mcp.NewToolResultError(fmt.Sprintf("decomposition failed: %v\n%s", err, string(output))), nil // nosec
	}
	return mcp.NewToolResultText(string(output)), nil
}

func (h *handler) getGraph(_ context.Context, _ mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	// 1. Get recent interactions from Metrics
	metrics, err := h.db.GetMetrics()
	if err != nil {
		return mcp.NewToolResultError("failed to get metrics for graph: " + err.Error()), nil
	}

	var sb strings.Builder
	sb.WriteString("graph LR\n")
	sb.WriteString("  subgraph Agents\n")
	
	agents := make(map[string]bool)
	tools := make(map[string]bool)
	interactions := make(map[string]bool)

	for _, m := range metrics {
		agent, _ := m["agent_name"].(string)
		tool, _ := m["tool_name"].(string)
		if agent != "" && tool != "" {
			agents[agent] = true
			tools[tool] = true
			interactions["    "+agent+" --> "+tool] = true
		}
	}

	for agent := range agents {
		sb.WriteString("    " + agent + "\n")
	}
	sb.WriteString("  end\n")

	sb.WriteString("  subgraph Tools\n")
	for tool := range tools {
		sb.WriteString("    " + tool + "\n")
	}
	sb.WriteString("  end\n")

	for edge := range interactions {
		sb.WriteString(edge + "\n")
	}

	// 2. Add Documentation Nodes
	sb.WriteString("  subgraph Wiki\n")
	filepath.Walk(filepath.Join(h.projectRoot, "wiki"), func(path string, info os.FileInfo, err error) error {
		if err == nil && !info.IsDir() && strings.HasSuffix(path, ".md") {
			rel, _ := filepath.Rel(h.projectRoot, path)
			sb.WriteString(fmt.Sprintf("    Docs[\"%s\"]\n", rel))
		}
		return nil
	})
	sb.WriteString("  end\n")
	
	return mcp.NewToolResultText(sb.String()), nil
}

func (h *handler) bmadStatus(_ context.Context, _ mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	files := []string{"BRIEF.md", "PRD.md", "ARCHITECTURE.md", "ROADMAP.md"}
	var status []string
	for _, f := range files {
		path := filepath.Join(h.projectRoot, "wiki", f)
		if _, err := os.Stat(path); err == nil {
			status = append(status, fmt.Sprintf("✅ %s: Present", f)) // nosec
		} else {
			status = append(status, fmt.Sprintf("❌ %s: Missing", f)) // nosec
		}
	}
	return mcp.NewToolResultText(strings.Join(status, "\n")), nil
}
