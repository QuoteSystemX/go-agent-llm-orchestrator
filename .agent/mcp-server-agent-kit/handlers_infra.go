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

func (h *handler) getAnalytics(_ context.Context, _ mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	path := filepath.Join(h.projectRoot, ".agent", "bus", "telemetry.json")
	data, err := os.ReadFile(path)
	if err != nil {
		return mcp.NewToolResultText("No telemetry data available yet."), nil
	}
	return mcp.NewToolResultText(string(data)), nil
}

func (h *handler) healthCheck(_ context.Context, _ mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	scriptPath := filepath.Join(h.projectRoot, ".agent", "scripts", "status_report.py")
	cmd := exec.Command("python3", scriptPath)
	cmd.Dir = h.projectRoot
	output, err := cmd.CombinedOutput()
	
	if err != nil {
		return mcp.NewToolResultError(fmt.Sprintf("health check failed: %v\n%s", err, string(output))), nil // nosec
	}
	return mcp.NewToolResultText(string(output)), nil
}

func (h *handler) healthFix(_ context.Context, _ mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	scriptPath := filepath.Join(h.projectRoot, ".agent", "scripts", "checklist.py")
	cmd := exec.Command("python3", scriptPath, ".", "--fix")
	cmd.Dir = h.projectRoot
	output, err := cmd.CombinedOutput()
	
	if err != nil {
		return mcp.NewToolResultError(fmt.Sprintf("health fix failed: %v\n%s", err, string(output))), nil // nosec
	}
	return mcp.NewToolResultText(string(output)), nil
}

func (h *handler) systemInfo(_ context.Context, _ mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	branch, _ := exec.Command("git", "rev-parse", "--abbrev-ref", "HEAD").Output()
	info := fmt.Sprintf("OS: %s\nArch: %s\nBranch: %s\nRoot: %s", // nosec
		os.Getenv("OS"), os.Getenv("PROCESSOR_ARCHITECTURE"), strings.TrimSpace(string(branch)), h.projectRoot)
	return mcp.NewToolResultText(info), nil
}

func (h *handler) setSecret(_ context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	key, _ := req.RequireString("key")
	val, _ := req.RequireString("value")
	if err := h.db.SetSecret(key, val); err != nil {
		return nil, err
	}
	return mcp.NewToolResultText("Secret stored."), nil
}

func (h *handler) getSecret(_ context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	key, _ := req.RequireString("key")
	val, err := h.db.GetSecret(key)
	if err != nil {
		return mcp.NewToolResultError("Secret not found: " + err.Error()), nil
	}
	return mcp.NewToolResultText(val), nil
}

func (h *handler) listProjects(_ context.Context, _ mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	projects, err := h.db.GetProjects()
	if err != nil {
		return nil, err
	}
	var lines []string
	for id, path := range projects {
		lines = append(lines, fmt.Sprintf("%s: %s", id, path)) // nosec
	}
	return mcp.NewToolResultText(strings.Join(lines, "\n")), nil
}


func (h *handler) backupS3(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	bucket, _ := req.RequireString("bucket")
	endpoint, _ := req.RequireString("endpoint")
	
	// Open DB file for reading
	dbPath := filepath.Join(h.projectRoot, ".agent", "mcp_server.db")
	f, err := os.Open(dbPath)
	if err != nil {
		return mcp.NewToolResultError("failed to open db for backup: " + err.Error()), nil
	}
	defer f.Close()

	// Logic for S3 upload would go here (using AWS SDK)
	fmt.Fprintf(os.Stderr, "Backing up %s to s3://%s at %s\n", dbPath, bucket, endpoint)
	
	return mcp.NewToolResultText("Backup initiated (simulated)."), nil
}

func (h *handler) registerWebhook(_ context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	url, _ := req.RequireString("url")
	events, _ := req.RequireString("events")
	
	id := fmt.Sprintf("WH-%d", time.Now().UnixNano()%1000)
	if err := h.db.AddWebhook(id, url, events); err != nil {
		return mcp.NewToolResultError("Failed to add webhook: " + err.Error()), nil
	}
	return mcp.NewToolResultText("Webhook registered: " + url), nil
}

func (h *handler) getMetrics(_ context.Context, _ mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	metrics, err := h.db.GetMetrics()
	if err != nil {
		return mcp.NewToolResultError("failed to get metrics: " + err.Error()), nil
	}
	var lines []string
	for _, m := range metrics {
		lines = append(lines, fmt.Sprintf("[%s] %s by %s: %vms", m["created"], m["tool"], m["agent"], m["duration"])) // nosec
	}
	if len(lines) == 0 {
		return mcp.NewToolResultText("No execution metrics available."), nil
	}
	return mcp.NewToolResultText(strings.Join(lines, "\n")), nil
}

func (h *handler) statusSummary(_ context.Context, _ mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	agents, _ := os.ReadDir(filepath.Join(h.projectRoot, ".agent", "agents"))
	skills, _ := os.ReadDir(filepath.Join(h.projectRoot, ".agent", "skills"))
	
	summary := fmt.Sprintf("Agents: %d\nSkills: %d", len(agents), len(skills))
	return mcp.NewToolResultText(summary), nil
}
