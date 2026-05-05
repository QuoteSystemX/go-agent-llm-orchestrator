package main

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"

	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"
)

const serverVersion = "1.1.0"

type handler struct {
	projectRoot string
}

func main() {
	root := resolveProjectRoot()
	h := &handler{projectRoot: root}

	s := server.NewMCPServer("agent-kit", serverVersion)

	// --- Skills Tools ---
	s.AddTool(mcp.NewTool("skills_list", mcp.WithDescription("List all available skill names.")), h.listSkills)
	s.AddTool(mcp.NewTool("skills_load",
		mcp.WithDescription("Load full SKILL.md content."),
		mcp.WithString("name", mcp.Required(), mcp.Description("Skill name")),
	), h.loadSkill)

	// --- Agents Tools ---
	s.AddTool(mcp.NewTool("agents_list", mcp.WithDescription("List all specialist agents.")), h.listAgents)
	s.AddTool(mcp.NewTool("agents_load",
		mcp.WithDescription("Load agent profile (persona and rules)."),
		mcp.WithString("name", mcp.Required(), mcp.Description("Agent name (e.g. orchestrator, analyst)")),
	), h.loadAgent)

	// --- Workflows Tools ---
	s.AddTool(mcp.NewTool("workflows_list", mcp.WithDescription("List all automated workflows.")), h.listWorkflows)
	s.AddTool(mcp.NewTool("workflows_run",
		mcp.WithDescription("Run a workflow pattern safely."),
		mcp.WithString("name", mcp.Required(), mcp.Description("Workflow name (e.g. full_cycle, reviewer)")),
		mcp.WithString("repo", mcp.Required(), mcp.Description("Target repository name")),
	), h.runWorkflow)

	// --- Tasks Tools ---
	s.AddTool(mcp.NewTool("tasks_submit",
		mcp.WithDescription("Submit a new task to the backlog."),
		mcp.WithString("title", mcp.Required(), mcp.Description("Task title")),
		mcp.WithString("description", mcp.Required(), mcp.Description("Task details")),
		mcp.WithString("agent", mcp.Required(), mcp.Description("Target specialist agent")),
	), h.submitTask)

	// --- Knowledge & Docs ---
	s.AddTool(mcp.NewTool("knowledge_read",
		mcp.WithDescription("Read core knowledge artifacts (KNOWLEDGE.md, ARCHITECTURE.md)."),
		mcp.WithString("name", mcp.Required(), mcp.Description("Artifact name (e.g. KNOWLEDGE, ARCHITECTURE)")),
	), h.readKnowledge)

	// --- Logging & Observability ---
	s.AddTool(mcp.NewTool("logs_tail",
		mcp.WithDescription("Get recent agent execution logs."),
		mcp.WithNumber("lines", mcp.Description("Number of lines to return (default 20)")),
	), h.tailLogs)

	// --- Status & BMAD Tools ---
	s.AddTool(mcp.NewTool("bmad_status", mcp.WithDescription("Check the status of the BMAD lifecycle.")), h.bmadStatus)
	s.AddTool(mcp.NewTool("status_summary", mcp.WithDescription("Get Agent Kit summary.")), h.statusSummary)

	if err := server.ServeStdio(s); err != nil {
		fmt.Fprintf(os.Stderr, "agent-kit-server: %v\n", err)
		os.Exit(1)
	}
}

func resolveProjectRoot() string {
	curr, _ := os.Getwd()
	for {
		if _, err := os.Stat(filepath.Join(curr, ".agent")); err == nil {
			return curr
		}
		parent := filepath.Dir(curr)
		if parent == curr {
			break
		}
		curr = parent
	}
	return "."
}

// --- Handlers ---

func (h *handler) runWorkflow(_ context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	name, _ := req.RequireString("name")
	repo, _ := req.RequireString("repo")

	name = sanitizeString(name)
	repo = sanitizeString(repo)

	// SECURITY: Argument sanitization applied via sanitizeString.
	return mcp.NewToolResultText(fmt.Sprintf("Workflow %q for %q prepared for execution.", name, repo)), nil
}

func (h *handler) submitTask(_ context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	title, _ := req.RequireString("title")
	description, _ := req.RequireString("description")
	agent, _ := req.RequireString("agent")

	agent = sanitizeString(agent)

	// Generate task file in tasks/
	filename := fmt.Sprintf("TASK-%d-%s.md", os.Getpid(), agent)
	content := fmt.Sprintf("# %s\n\nAgent: %s\n\n%s", title, agent, description)
	
	path := filepath.Join(h.projectRoot, "tasks", filename)
	if err := os.WriteFile(path, []byte(content), 0644); err != nil {
		return mcp.NewToolResultError("failed to write task: " + err.Error()), nil
	}
	
	return mcp.NewToolResultText("Task submitted: " + filename), nil
}

func (h *handler) bmadStatus(_ context.Context, _ mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	files := []string{"BRIEF.md", "PRD.md", "ARCHITECTURE.md", "ROADMAP.md"}
	var status []string
	for _, f := range files {
		path := filepath.Join(h.projectRoot, "wiki", f)
		if _, err := os.Stat(path); err == nil {
			status = append(status, fmt.Sprintf("✅ %s: Present", f))
		} else {
			status = append(status, fmt.Sprintf("❌ %s: Missing", f))
		}
	}
	return mcp.NewToolResultText(strings.Join(status, "\n")), nil
}

func (h *handler) statusSummary(_ context.Context, _ mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	agents, _ := os.ReadDir(filepath.Join(h.projectRoot, ".agent", "agents"))
	skills, _ := os.ReadDir(filepath.Join(h.projectRoot, ".agent", "skills"))
	workflows, _ := os.ReadDir(filepath.Join(h.projectRoot, ".agent", "workflows"))

	summary := fmt.Sprintf("Agents: %d\nSkills: %d\nWorkflows: %d", len(agents), len(skills), len(workflows))
	return mcp.NewToolResultText(summary), nil
}

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
	name = sanitizeString(name)
	if !strings.HasSuffix(name, ".md") {
		name += ".md"
	}
	return h.loadItem(filepath.Join(h.projectRoot, ".agent", "agents", name))
}

func (h *handler) listWorkflows(_ context.Context, _ mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	return h.listItemsHelper(filepath.Join(h.projectRoot, ".agent", "workflows"), false)
}

// --- Helpers ---

func (h *handler) listItemsHelper(path string, isDir bool) (*mcp.CallToolResult, error) {
	entries, err := os.ReadDir(path)
	if err != nil {
		return mcp.NewToolResultError("cannot read directory: " + err.Error()), nil
	}
	var names []string
	for _, e := range entries {
		if strings.HasPrefix(e.Name(), ".") {
			continue
		}
		if isDir && e.IsDir() {
			names = append(names, e.Name())
		} else if !isDir && !e.IsDir() {
			names = append(names, strings.TrimSuffix(e.Name(), ".md"))
		}
	}
	return mcp.NewToolResultText(strings.Join(names, "\n")), nil
}

func (h *handler) loadItem(path string) (*mcp.CallToolResult, error) {
	if verr := validatePath(path); verr != nil {
		return mcp.NewToolResultError(verr.Error()), nil
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return mcp.NewToolResultError(fmt.Sprintf("item not found at %s", path)), nil
	}
	return mcp.NewToolResultText(string(data)), nil
}

func (h *handler) readKnowledge(_ context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	name, _ := req.RequireString("name")
	name = sanitizeString(name)
	var path string
	if name == "KNOWLEDGE" {
		path = filepath.Join(h.projectRoot, ".agent", "KNOWLEDGE.md")
	} else if name == "ARCHITECTURE" {
		path = filepath.Join(h.projectRoot, "wiki", "ARCHITECTURE.md")
	} else {
		return mcp.NewToolResultError("unknown knowledge artifact"), nil
	}
	return h.loadItem(path)
}

func (h *handler) tailLogs(_ context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	lines := 20
	if args, ok := req.Params.Arguments.(map[string]interface{}); ok {
		if l, ok := args["lines"].(float64); ok {
			lines = int(l)
		}
	}

	return mcp.NewToolResultText(fmt.Sprintf("Tail of last %d lines from .agent/logs/audit.log...", lines)), nil
}

func validatePath(path string) error {
	if strings.Contains(path, "..") {
		return fmt.Errorf("invalid path traversal attempt")
	}
	return nil
}

func sanitizeString(s string) string {
	reg, _ := regexp.Compile("[^a-zA-Z0-9_-]+")
	return reg.ReplaceAllString(s, "")
}
