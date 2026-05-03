package main

import (
	"context"
	"os"
	"path/filepath"
	"strings"

	"github.com/mark3labs/mcp-go/mcp"
)

func (h *handler) listSkills(_ context.Context, _ mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	return h.listItemsHelper(filepath.Join(h.projectRoot, ".agent", "skills"), true)
}

func (h *handler) loadSkill(_ context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	name, _ := req.RequireString("name")
	return h.loadItem(filepath.Join(h.projectRoot, ".agent", "skills", sanitizeString(name), "SKILL.md"))
}

func (h *handler) listAgents(_ context.Context, _ mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	return h.listItemsHelper(filepath.Join(h.projectRoot, ".agent", "agents"), false)
}

func (h *handler) loadAgent(_ context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	name, _ := req.RequireString("name")
	return h.loadItem(filepath.Join(h.projectRoot, ".agent", "agents", sanitizeString(name)+".md"))
}

func (h *handler) searchSkills(_ context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	query, _ := req.RequireString("query")
	query = strings.ToLower(strings.TrimSpace(query))
	if query == "" {
		return mcp.NewToolResultError("query cannot be empty"), nil
	}

	skillsDir := filepath.Join(h.projectRoot, ".agent", "skills")
	entries, err := os.ReadDir(skillsDir)
	if err != nil {
		return mcp.NewToolResultError("cannot read skills directory: " + err.Error()), nil
	}

	var matches []string
	for _, e := range entries {
		if !e.IsDir() || strings.HasPrefix(e.Name(), ".") {
			continue
		}
		name := e.Name()
		// Match against skill directory name first.
		if strings.Contains(strings.ToLower(name), query) {
			matches = append(matches, name)
			continue
		}
		// Then scan the first 512 bytes of SKILL.md for the keyword.
		skillPath := filepath.Join(skillsDir, name, "SKILL.md")
		f, err := os.Open(skillPath)
		if err != nil {
			continue
		}
		preview := make([]byte, 512)
		nr, _ := f.Read(preview)
		f.Close()
		if strings.Contains(strings.ToLower(string(preview[:nr])), query) {
			matches = append(matches, name)
		}
	}

	if len(matches) == 0 {
		return mcp.NewToolResultText("no skills found matching: " + query), nil
	}
	return mcp.NewToolResultText(strings.Join(matches, "\n")), nil
}
