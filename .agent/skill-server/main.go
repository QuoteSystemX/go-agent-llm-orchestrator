package main

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"
)

const serverVersion = "1.0.0"

type handler struct{ root string }

func main() {
	h := &handler{root: resolveSkillsRoot()}

	s := server.NewMCPServer("skills", serverVersion)

	s.AddTool(
		mcp.NewTool("skills_load",
			mcp.WithDescription("Load full SKILL.md content by skill name. "+
				"Call this before working on a task to read the required skill knowledge."),
			mcp.WithString("name",
				mcp.Required(),
				mcp.Description("Skill name, e.g. clean-code, api-patterns, systematic-debugging"),
			),
		),
		h.load,
	)

	s.AddTool(
		mcp.NewTool("skills_list",
			mcp.WithDescription("List all available skill names in the Antigravity Kit."),
		),
		h.list,
	)

	s.AddTool(
		mcp.NewTool("skills_search",
			mcp.WithDescription("Find skills by keyword. Searches both skill names and SKILL.md content."),
			mcp.WithString("query",
				mcp.Required(),
				mcp.Description("Keyword to search for, e.g. authentication, kubernetes, testing"),
			),
		),
		h.search,
	)

	if err := server.ServeStdio(s); err != nil {
		fmt.Fprintf(os.Stderr, "skill-server: %v\n", err)
		os.Exit(1)
	}
}

// resolveSkillsRoot finds .agent/skills relative to CWD (Claude Code launches
// MCP servers from the project root) or falls back to a path relative to the binary.
func resolveSkillsRoot() string {
	if _, err := os.Stat(".agent/skills"); err == nil {
		return ".agent/skills"
	}
	// Binary is at .agent/skill-server/bin/<name> → skills at ../../skills
	exe, err := os.Executable()
	if err != nil {
		return ".agent/skills"
	}
	return filepath.Join(filepath.Dir(exe), "..", "..", "skills")
}

func (h *handler) load(_ context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	name, err := req.RequireString("name")
	if err != nil {
		return mcp.NewToolResultError(err.Error()), nil
	}
	if verr := validateName(name); verr != nil {
		return mcp.NewToolResultError(verr.Error()), nil
	}
	data, err := os.ReadFile(filepath.Join(h.root, name, "SKILL.md"))
	if err != nil {
		return mcp.NewToolResultError(fmt.Sprintf("skill %q not found", name)), nil
	}
	return mcp.NewToolResultText(string(data)), nil
}

func (h *handler) list(_ context.Context, _ mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	entries, err := os.ReadDir(h.root)
	if err != nil {
		return mcp.NewToolResultError("cannot read skills directory: " + err.Error()), nil
	}
	var names []string
	for _, e := range entries {
		if e.IsDir() {
			if _, err := os.Stat(filepath.Join(h.root, e.Name(), "SKILL.md")); err == nil {
				names = append(names, e.Name())
			}
		}
	}
	return mcp.NewToolResultText(strings.Join(names, "\n")), nil
}

func (h *handler) search(_ context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	query, err := req.RequireString("query")
	if err != nil {
		return mcp.NewToolResultError(err.Error()), nil
	}
	q := strings.ToLower(query)

	entries, err := os.ReadDir(h.root)
	if err != nil {
		return mcp.NewToolResultError("cannot read skills directory: " + err.Error()), nil
	}

	var matches []string
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		name := e.Name()
		if strings.Contains(strings.ToLower(name), q) {
			matches = append(matches, name)
			continue
		}
		data, err := os.ReadFile(filepath.Join(h.root, name, "SKILL.md"))
		if err != nil {
			continue
		}
		if strings.Contains(strings.ToLower(string(data)), q) {
			matches = append(matches, name)
		}
	}

	if len(matches) == 0 {
		return mcp.NewToolResultText("(no matching skills for: " + query + ")"), nil
	}
	return mcp.NewToolResultText(strings.Join(matches, "\n")), nil
}

// validateName rejects traversal attempts; skill names must be simple identifiers.
func validateName(name string) error {
	if name != filepath.Base(name) || strings.HasPrefix(name, ".") {
		return fmt.Errorf("invalid skill name %q", name)
	}
	return nil
}
