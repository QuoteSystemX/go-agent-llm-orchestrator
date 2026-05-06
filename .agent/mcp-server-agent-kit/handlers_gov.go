package main

import (
	"context"
	"fmt"
	"path/filepath"
	"strings"
	"time"

	"github.com/mark3labs/mcp-go/mcp"
)

func (h *handler) listProposals(_ context.Context, _ mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	ps, err := h.db.GetProposals()
	if err != nil {
		return mcp.NewToolResultError("failed to get proposals: " + err.Error()), nil
	}

	var lines []string
	for _, p := range ps {
		lines = append(lines, fmt.Sprintf("[%s] %s: %d/%d votes - %s", p.ID, p.Title, p.Votes, p.Required, p.Status)) // nosec
	}
	if len(lines) == 0 {
		return mcp.NewToolResultText("No active proposals."), nil
	}
	return mcp.NewToolResultText(strings.Join(lines, "\n")), nil
}

func (h *handler) voteProposal(_ context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	id, _ := req.RequireString("id")
	
	ps, err := h.db.GetProposals()
	if err != nil {
		return mcp.NewToolResultError("db error: " + err.Error()), nil
	}

	var target *CouncilProposal
	for _, p := range ps {
		if p.ID == id {
			target = p
			break
		}
	}

	if target == nil {
		return mcp.NewToolResultError("Proposal not found"), nil
	}

	target.Votes++
	if target.Votes >= target.Required {
		target.Status = "approved"
	}

	if err := h.db.SaveProposal(target); err != nil {
		return mcp.NewToolResultError("failed to save vote: " + err.Error()), nil
	}

	return mcp.NewToolResultText(fmt.Sprintf("Vote cast for %s. Current status: %d/%d", target.Title, target.Votes, target.Required)), nil // nosec
}

func (h *handler) createProposal(_ context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	title, _ := req.RequireString("title")
	id := fmt.Sprintf("PROP-%d", time.Now().UnixNano()%10000)
	
	p := &CouncilProposal{
		ID:        id,
		Title:     title,
		Proposer:  "Human Operator",
		Votes:     0,
		Required:  3,
		Status:    "open",
		CreatedAt: time.Now(),
	}

	if err := h.db.SaveProposal(p); err != nil {
		return mcp.NewToolResultError("failed to create proposal: " + err.Error()), nil
	}

	return mcp.NewToolResultText(fmt.Sprintf("Proposal created: %s (ID: %s)", title, id)), nil // nosec
}

func (h *handler) executeProposal(_ context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	id, _ := req.RequireString("id")
	
	ps, err := h.db.GetProposals()
	if err != nil {
		return mcp.NewToolResultError("db error: " + err.Error()), nil
	}

	var target *CouncilProposal
	for _, p := range ps {
		if p.ID == id {
			target = p
			break
		}
	}

	if target == nil {
		return mcp.NewToolResultError("Proposal not found"), nil
	}

	if target.Status != "approved" {
		return mcp.NewToolResultError(fmt.Sprintf("Proposal is not approved. Current status: %s", target.Status)), nil // nosec
	}

	if target.CommandType == "" {
		return mcp.NewToolResultError("Proposal has no executable command associated with it"), nil
	}

	// Actually execute based on command type
	switch target.CommandType {
	case "security_fix":
		parts := strings.Split(target.CommandData, "|")
		if len(parts) != 2 {
			return mcp.NewToolResultError("invalid command data for security_fix"), nil
		}
		vID, path := parts[0], parts[1]
		
		jobID := fmt.Sprintf("FIX-%d", time.Now().UnixNano()%10000)
		job := &JobStatus{
			ID:        jobID,
			Name:      fmt.Sprintf("Approved Fix %s", vID), // nosec
			Status:    "running",
			StartedAt: time.Now(),
			Progress:  0,
			Message:   fmt.Sprintf("Executing approved patch for %s...", path), // nosec
		}
		h.db.SaveJob(job)

		scriptPath := filepath.Join(h.projectRoot, ".agent", "scripts", "vulnerability_patcher.py")
		h.dispatcher.Submit(Task{
			JobID:   jobID,
			Command: "python3",
			Args:    []string{scriptPath, "--vulnerability", vID, "--file", path},
			Dir:     h.projectRoot,
		})
		
		target.Status = "executed"
		h.db.SaveProposal(target)
		return mcp.NewToolResultText(fmt.Sprintf("Approved action 'security_fix' started. Job ID: %s", jobID)), nil // nosec

	default:
		return mcp.NewToolResultError("Unsupported command type: " + target.CommandType), nil
	}
}

func (h *handler) securityFix(_ context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	vID, _ := req.RequireString("vulnerability_id")
	path, _ := req.RequireString("file_path")
	
	proposalID := fmt.Sprintf("SEC-%d", time.Now().UnixNano()%10000)
	p := &CouncilProposal{
		ID:          proposalID,
		Title:       fmt.Sprintf("Apply Security Patch %s to %s", vID, path), // nosec
		Proposer:    "AI Agent",
		Votes:       0,
		Required:    2, // Security fixes require fewer votes for agility
		Status:      "open",
		CreatedAt:   time.Now(),
		CommandType: "security_fix",
		CommandData: fmt.Sprintf("%s|%s", vID, path), // nosec
	}
	
	h.db.SaveProposal(p)
	return mcp.NewToolResultText(fmt.Sprintf("Action 'security_fix' intercepted. Security changes require council approval.\nCreated Proposal: %s\nRun 'council_vote' to approve.", proposalID)), nil // nosec
}

func (h *handler) setPermission(_ context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	agent, _ := req.RequireString("agent")
	tool, _ := req.RequireString("tool")
	allowed, _ := req.RequireBool("allowed")
	
	if err := h.db.SetPermission(agent, tool, allowed); err != nil {
		return mcp.NewToolResultError("failed to set permission: " + err.Error()), nil
	}
	return mcp.NewToolResultText(fmt.Sprintf("Permission for %s on %s set to %v", agent, tool, allowed)), nil // nosec
}
