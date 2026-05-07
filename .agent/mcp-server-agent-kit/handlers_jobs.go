package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	"github.com/mark3labs/mcp-go/mcp"
)

func (h *handler) runWorkflow(_ context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	name, _ := req.RequireString("name")
	argsStr, _ := req.RequireString("arguments")

	// Strip script extensions sent by the plugin UI (e.g. "reviewer.py" → "reviewer").
	for _, ext := range []string{".py", ".sh", ".js"} {
		name = strings.TrimSuffix(name, ext)
	}
	name = sanitizeString(name)

	// Security: only allow names that correspond to a known workflow .md file.
	workflowMD := filepath.Join(h.projectRoot, ".agent", "workflows", name+".md")
	if _, err := os.Stat(workflowMD); err != nil {
		return mcp.NewToolResultError(fmt.Sprintf("workflow %q not found in .agent/workflows/", name)), nil
	}

	// Resolve associated Python script in .agent/scripts/.
	scriptPath := filepath.Join(h.projectRoot, ".agent", "scripts", name+".py")
	if _, err := os.Stat(scriptPath); err != nil {
		return mcp.NewToolResultText(fmt.Sprintf(
			`{"status":"instructions_only","workflow":%q,"note":"no executable script; use knowledge_read to load workflow instructions"}`,
			name,
		)), nil
	}

	jobID := fmt.Sprintf("WORKFLOW-%d", time.Now().UnixNano())

	err := h.db.SaveJob(&JobStatus{
		ID:        jobID,
		Name:      "Workflow: " + name,
		Status:    "pending",
		StartedAt: time.Now(),
	})
	if err != nil {
		return nil, err
	}

	var extraArgs []string
	if argsStr != "" {
		extraArgs = strings.Fields(argsStr)
	}

	if err := h.dispatcher.Submit(Task{ // nosec
		JobID:   jobID,
		Command: "python3",
		Args:    append([]string{scriptPath}, extraArgs...),
		Dir:     h.projectRoot,
	}); err != nil {
		h.finishJob(jobID, "failed")
		return mcp.NewToolResultError("failed to queue workflow \"" + name + "\": " + err.Error()), nil
	}

	return mcp.NewToolResultText(fmt.Sprintf(`{"job_id":%q,"status":"running","workflow":%q}`, jobID, name)), nil // nosec
}

func (h *handler) readWorkflowDoc(_ context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	name, _ := req.RequireString("name")
	name = sanitizeString(name)
	workflowMD := filepath.Join(h.projectRoot, ".agent", "workflows", name+".md")
	content, err := os.ReadFile(workflowMD)
	if err != nil {
		return mcp.NewToolResultError(fmt.Sprintf("workflow %q not found", name)), nil
	}
	return mcp.NewToolResultText(string(content)), nil
}

func (h *handler) listWorkflows(_ context.Context, _ mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	workflowsDir := filepath.Join(h.projectRoot, ".agent", "workflows")
	entries, err := os.ReadDir(workflowsDir)
	if err != nil {
		return mcp.NewToolResultError("cannot read .agent/workflows/: " + err.Error()), nil
	}
	var workflows []WorkflowInfo
	for _, e := range entries {
		if !e.IsDir() && strings.HasSuffix(e.Name(), ".md") {
			id := strings.TrimSuffix(e.Name(), ".md")
			fullPath := filepath.Join(workflowsDir, e.Name())

			info := h.parseWorkflowInfo(id, fullPath)

			// Mark workflows that have an associated executable script.
			scriptPath := filepath.Join(h.projectRoot, ".agent", "scripts", id+".py")
			if _, err := os.Stat(scriptPath); err == nil {
				info.Executable = true
			}

			workflows = append(workflows, info)
		}
	}

	data, err := json.MarshalIndent(workflows, "", "  ")
	if err != nil {
		return mcp.NewToolResultError("failed to marshal workflows: " + err.Error()), nil
	}

	return mcp.NewToolResultText(string(data)), nil
}

func (h *handler) parseWorkflowInfo(id, path string) WorkflowInfo {
	info := WorkflowInfo{
		ID:          id,
		Name:        strings.Title(strings.ReplaceAll(id, "-", " ")), // fallback
		Description: "No description provided.",                     // fallback
		Phase:       "utility",                                       // fallback
		Args:        ".",                                             // fallback
	}

	content, err := os.ReadFile(path)
	if err != nil {
		return info
	}

	// Simple frontmatter parser
	re := regexp.MustCompile(`(?s)^---\s*\n(.*?)\n---\s*`)
	match := re.FindStringSubmatch(string(content))
	if len(match) < 2 {
		return info
	}

	lines := strings.Split(match[1], "\n")
	for _, line := range lines {
		parts := strings.SplitN(line, ":", 2)
		if len(parts) < 2 {
			continue
		}
		key := strings.TrimSpace(parts[0])
		val := strings.TrimSpace(parts[1])
		// Remove quotes if present
		val = strings.Trim(val, `"'`)

		switch key {
		case "name":
			info.Name = val
		case "description":
			info.Description = val
		case "phase":
			info.Phase = val
		case "args":
			info.Args = val
		}
	}

	return info
}

func (h *handler) listJobs(_ context.Context, _ mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	jobs, err := h.db.GetJobs()
	if err != nil {
		return nil, err
	}
	var lines []string
	for _, j := range jobs {
		lines = append(lines, fmt.Sprintf("%s [%s]: %s (%d%%) - %s", j.ID, j.Status, j.Name, j.Progress, j.Message)) // nosec
	}
	return mcp.NewToolResultText(strings.Join(lines, "\n")), nil
}

func (h *handler) getJobStatus(_ context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	id, _ := req.RequireString("id")
	jobs, err := h.db.GetJobs()
	if err != nil {
		return nil, err
	}
	for _, j := range jobs {
		if j.ID == id {
			return mcp.NewToolResultText(fmt.Sprintf("Job: %s\nStatus: %s\nProgress: %d%%\nMessage: %s", j.ID, j.Status, j.Progress, j.Message)), nil // nosec
		}
	}
	return mcp.NewToolResultError("Job not found"), nil
}

func (h *handler) submitTask(_ context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	title, _ := req.RequireString("title")
	description, _ := req.RequireString("description")
	agent, _ := req.RequireString("agent")

	agent = sanitizeString(agent)

	filename := fmt.Sprintf("%s-%s-%d.md", time.Now().Format("2006-01-02"), agent, time.Now().UnixNano()%1e9) // nosec
	content := fmt.Sprintf("# %s\n\nAgent: %s\n\n%s\n", title, agent, description) // nosec

	tasksDir := filepath.Join(h.projectRoot, "tasks")
	if err := os.MkdirAll(tasksDir, 0o755); err != nil {
		return mcp.NewToolResultError("failed to create tasks directory: " + err.Error()), nil
	}
	if err := os.WriteFile(filepath.Join(tasksDir, filename), []byte(content), 0o644); err != nil { // nosec
		return mcp.NewToolResultError("failed to write task: " + err.Error()), nil
	}

	return mcp.NewToolResultText("Task submitted: " + filename), nil
}
