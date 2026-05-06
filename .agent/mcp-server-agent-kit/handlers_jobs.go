package main

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
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
		return mcp.NewToolResultError(fmt.Sprintf("failed to queue workflow %q: %v", name, err)), nil
	}

	return mcp.NewToolResultText(fmt.Sprintf(`{"job_id":%q,"status":"running","workflow":%q}`, jobID, name)), nil // nosec
}

func (h *handler) listWorkflows(_ context.Context, _ mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	workflowsDir := filepath.Join(h.projectRoot, ".agent", "workflows")
	entries, err := os.ReadDir(workflowsDir)
	if err != nil {
		return mcp.NewToolResultError("cannot read .agent/workflows/: " + err.Error()), nil
	}
	var workflows []string
	for _, e := range entries {
		if !e.IsDir() && strings.HasSuffix(e.Name(), ".md") {
			name := strings.TrimSuffix(e.Name(), ".md")
			// Mark workflows that have an associated executable script.
			scriptPath := filepath.Join(h.projectRoot, ".agent", "scripts", name+".py")
			marker := " [instructions-only]"
			if _, err := os.Stat(scriptPath); err == nil {
				marker = " [executable]"
			}
			workflows = append(workflows, name+marker)
		}
	}
	return mcp.NewToolResultText(strings.Join(workflows, "\n")), nil
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
