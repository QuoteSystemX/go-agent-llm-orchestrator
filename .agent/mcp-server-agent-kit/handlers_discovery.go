package main

import (
	"context"
	"encoding/json"
	"io/fs"
	"os"
	"path/filepath"
	"strings"

	"github.com/mark3labs/mcp-go/mcp"
)

func (h *handler) listSkills(_ context.Context, _ mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	skillsDir := filepath.Join(h.projectRoot, ".agent", "skills")
	entries, err := os.ReadDir(skillsDir)
	if err != nil {
		return mcp.NewToolResultError("cannot read skills directory: " + err.Error()), nil
	}

	var infos []RegistryInfo
	for _, e := range entries {
		if !e.IsDir() || strings.HasPrefix(e.Name(), ".") {
			continue
		}
		id := e.Name()
		skillMD := filepath.Join(skillsDir, id, "SKILL.md")
		content, _ := os.ReadFile(skillMD)
		meta := parseFrontmatter(string(content))

		name := meta["name"]
		if name == "" {
			name = strings.Title(strings.ReplaceAll(id, "-", " "))
		}

		infos = append(infos, RegistryInfo{
			ID:          id,
			Name:        name,
			Description: meta["description"],
			Type:        "skill",
		})
	}

	jsonData, _ := json.Marshal(infos)
	return mcp.NewToolResultText(string(jsonData)), nil
}

func (h *handler) loadSkill(_ context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	name, _ := req.RequireString("name")
	return h.loadItem(filepath.Join(h.projectRoot, ".agent", "skills", sanitizeString(name), "SKILL.md"))
}

func (h *handler) listAgents(_ context.Context, _ mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	agentsRoot := filepath.Join(h.projectRoot, ".agent", "agents")
	var infos []RegistryInfo
	_ = filepath.WalkDir(agentsRoot, func(path string, d fs.DirEntry, err error) error {
		if err != nil || d.IsDir() || strings.HasPrefix(d.Name(), ".") {
			return nil
		}
		if strings.HasSuffix(d.Name(), ".md") {
			id := strings.TrimSuffix(d.Name(), ".md")
			content, _ := os.ReadFile(path)
			meta := parseFrontmatter(string(content))

			name := meta["name"]
			if name == "" {
				name = strings.Title(strings.ReplaceAll(id, "-", " "))
			}

			infos = append(infos, RegistryInfo{
				ID:          id,
				Name:        name,
				Description: meta["description"],
				Type:        "agent",
			})
		}
		return nil
	})
	jsonData, _ := json.Marshal(infos)
	return mcp.NewToolResultText(string(jsonData)), nil
}

func (h *handler) loadAgent(_ context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	name, _ := req.RequireString("name")
	name = sanitizeString(name)
	// Recursive search through category subfolders
	agentsRoot := filepath.Join(h.projectRoot, ".agent", "agents")
	var found string
	_ = filepath.WalkDir(agentsRoot, func(path string, d fs.DirEntry, _ error) error {
		if !d.IsDir() && d.Name() == name+".md" {
			found = path
			return fs.SkipAll
		}
		return nil
	})
	if found == "" {
		return mcp.NewToolResultError("agent not found: " + name), nil
	}
	return h.loadItem(found)
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
