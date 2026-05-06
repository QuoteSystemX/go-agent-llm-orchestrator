package main

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"github.com/mark3labs/mcp-go/mcp"
)

func (h *handler) loadItem(path string) (*mcp.CallToolResult, error) {
	// Defense-in-depth: verify resolved path stays within project root.
	clean := filepath.Clean(path)
	root := filepath.Clean(h.projectRoot)
	rel, err := filepath.Rel(root, clean)
	if err != nil || strings.HasPrefix(rel, "..") {
		return mcp.NewToolResultError("access denied: path outside project root"), nil
	}

	// Trigger on_read hooks
	h.indexer.TriggerHooks(rel, "on_read", clean, "READ-HOOK")

	data, err := os.ReadFile(clean)
	if err != nil {
		return mcp.NewToolResultError(fmt.Sprintf("item not found at %s", path)), nil // nosec
	}
	return mcp.NewToolResultText(string(data)), nil
}

func (h *handler) searchKnowledge(_ context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	query, _ := req.RequireString("query")
	
	scriptPath := filepath.Join(h.projectRoot, ".agent", "scripts", "semantic_brain_engine.py")
	cmd := exec.Command("python3", scriptPath, query)
	cmd.Dir = h.projectRoot
	output, err := cmd.CombinedOutput()
	
	if err != nil {
		return mcp.NewToolResultError(fmt.Sprintf("search failed: %v\n%s", err, string(output))), nil // nosec
	}
	return mcp.NewToolResultText(string(output)), nil
}

func (h *handler) readKnowledge(_ context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	name, _ := req.RequireString("name")
	name = sanitizeString(name)
	var path string
	if name == "KNOWLEDGE" {
		path = filepath.Join(h.projectRoot, ".agent", "KNOWLEDGE.md")
	} else if name == "ARCHITECTURE" {
		path = filepath.Join(h.projectRoot, ".agent", "ARCHITECTURE.md")
	} else {
		return mcp.NewToolResultError("unknown knowledge artifact; valid values: KNOWLEDGE, ARCHITECTURE"), nil
	}
	return h.loadItem(path)
}

func (h *handler) searchFullText(_ context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	query, _ := req.RequireString("query")
	results, err := h.indexer.Search(query)
	if err != nil {
		return mcp.NewToolResultError("Search failed: " + err.Error()), nil
	}
	
	if len(results) == 0 {
		return mcp.NewToolResultText("No matches found."), nil
	}

	var lines []string
	for _, res := range results {
		lines = append(lines, fmt.Sprintf("[%s] %s: %s", res["type"], res["path"], res["snippet"])) // nosec
	}
	return mcp.NewToolResultText(strings.Join(lines, "\n")), nil
}

func (h *handler) tailLogs(_ context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	n := 20
	if args, ok := req.Params.Arguments.(map[string]any); ok {
		if l, ok := args["lines"].(float64); ok && l > 0 {
			n = int(l)
		}
	}

	logsDir := filepath.Join(h.projectRoot, ".agent", "logs")
	entries, err := os.ReadDir(logsDir)
	if err != nil {
		return mcp.NewToolResultText("no log directory found at .agent/logs/"), nil
	}

	// Find newest .log file by modification time.
	var latestPath string
	var latestMod time.Time
	for _, e := range entries {
		if e.IsDir() || !strings.HasSuffix(e.Name(), ".log") {
			continue
		}
		info, err := e.Info()
		if err == nil && info.ModTime().After(latestMod) {
			latestMod = info.ModTime()
			latestPath = filepath.Join(logsDir, e.Name())
		}
	}
	if latestPath == "" {
		return mcp.NewToolResultText("no .log files found in .agent/logs/"), nil
	}

	data, err := os.ReadFile(latestPath)
	if err != nil {
		return mcp.NewToolResultError("cannot read log: " + err.Error()), nil
	}

	all := strings.Split(strings.TrimSpace(string(data)), "\n")
	if len(all) > n {
		all = all[len(all)-n:]
	}

	return mcp.NewToolResultText(fmt.Sprintf("=== %s (last %d lines) ===\n%s", // nosec
		filepath.Base(latestPath), n, strings.Join(all, "\n"))), nil
}

