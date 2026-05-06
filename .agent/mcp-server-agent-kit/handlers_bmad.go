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
	// Simple graph generation from file structure (recursive)
	var sb strings.Builder
	sb.WriteString("graph TD\n")
	
	filepath.Walk(h.projectRoot, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() || !strings.HasSuffix(path, ".md") {
			return nil
		}
		rel, _ := filepath.Rel(h.projectRoot, path)
		sb.WriteString(fmt.Sprintf("  Node%d[\"%s\"]\n", len(rel), rel))
		return nil
	})
	
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
