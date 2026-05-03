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

func (h *handler) runWorkflow(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	name, _ := req.RequireString("name")
	argsStr, _ := req.RequireString("arguments")
	
	jobID := fmt.Sprintf("WORKFLOW-%d", time.Now().UnixNano())
	
	// Register job in DB
	err := h.db.SaveJob(&JobStatus{
		ID:        jobID,
		Name:      "Workflow: " + name,
		Status:    "pending",
		StartedAt: time.Now(),
	})
	if err != nil {
		return nil, err
	}

	// Submit to worker pool
	h.dispatcher.Submit(Task{
		JobID:   jobID,
		Command: filepath.Join(h.projectRoot, ".agent", "scripts", name),
		Args:    strings.Split(argsStr, " "),
	})

	return mcp.NewToolResultText(fmt.Sprintf("Workflow %s initiated. Job ID: %s", name, jobID)), nil
}

func (h *handler) listWorkflows(_ context.Context, _ mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	scriptsDir := filepath.Join(h.projectRoot, ".agent", "scripts")
	entries, err := os.ReadDir(scriptsDir)
	if err != nil {
		return nil, err
	}
	var workflows []string
	for _, e := range entries {
		if !e.IsDir() && (strings.HasSuffix(e.Name(), ".sh") || strings.HasSuffix(e.Name(), ".py")) {
			workflows = append(workflows, e.Name())
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
		lines = append(lines, fmt.Sprintf("%s [%s]: %s (%d%%) - %s", j.ID, j.Status, j.Name, j.Progress, j.Message))
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
			return mcp.NewToolResultText(fmt.Sprintf("Job: %s\nStatus: %s\nProgress: %d%%\nMessage: %s", j.ID, j.Status, j.Progress, j.Message)), nil
		}
	}
	return mcp.NewToolResultError("Job not found"), nil
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
