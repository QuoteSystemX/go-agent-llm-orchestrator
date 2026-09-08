package main

import (
	"context"
	"fmt"
	"path/filepath"
	"slices"
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
		// Format: [ID] Title: Votes/Required votes - Status | Proposer | CommandType | CommandData
		lines = append(lines, fmt.Sprintf("[%s] %s: %d/%d votes - %s | %s | %s | %s", p.ID, p.Title, p.Votes, p.Required, p.Status, p.Proposer, p.CommandType, p.CommandData)) // nosec
	}
	if len(lines) == 0 {
		return mcp.NewToolResultText("No active proposals."), nil
	}
	return mcp.NewToolResultText(strings.Join(lines, "\n")), nil
}

func (h *handler) voteProposal(_ context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	id, _ := req.RequireString("id")

	// Same implicit caller-identity convention withRBAC already uses for
	// permission checks — reused here so one calling agent can't inflate a
	// proposal's vote count past `required` by calling council_vote repeatedly.
	voter := ""
	if args, ok := req.Params.Arguments.(map[string]any); ok {
		if a, ok := args["_agent"].(string); ok {
			voter = a
		}
	}
	if voter == "" || voter == "unknown" {
		return mcp.NewToolResultError("Vote rejected: caller identity (_agent) could not be determined"), nil
	}

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

	// Lift-a-veto proposals draw from a closed pool, not "anyone with council_vote
	// permission" — and specifically exclude the veto's own creator (ethics-auditor), so a
	// veto can never be self-lifted. This is business logic, not RBAC: CheckPermission is
	// default-allow (see db_security.go), so a role restriction like this can only live here,
	// not as a `permissions` table row.
	if target.CommandType == "lift_ethics_veto" {
		eligible := map[string]bool{"risk-manager": true, "cto": true, "security-auditor": true}
		if !eligible[voter] {
			return mcp.NewToolResultError(fmt.Sprintf(
				"Vote rejected: %s is not eligible to vote on lifting an ethics veto (eligible: risk-manager, cto, security-auditor — the vetoing ethics-auditor cannot vote on its own lift)", voter,
			)), nil // nosec
		}
	}

	if slices.Contains(target.Voters, voter) {
		return mcp.NewToolResultText(fmt.Sprintf("%s already voted on %s — vote not counted twice. Current status: %d/%d", voter, target.Title, target.Votes, target.Required)), nil // nosec
	}

	target.Voters = append(target.Voters, voter)
	target.Votes++
	if target.Votes >= target.Required {
		target.Status = "approved"
	}

	if err := h.db.SaveProposal(target); err != nil {
		return mcp.NewToolResultError("failed to save vote: " + err.Error()), nil
	}

	return mcp.NewToolResultText(fmt.Sprintf("Vote cast by %s for %s. Current status: %d/%d", voter, target.Title, target.Votes, target.Required)), nil // nosec
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

	case "lift_ethics_veto":
		// Pure state transition — unlike "security_fix" above, there is no job to dispatch.
		// CommandData holds the VetoRecord ID (set by ethicsVeto()).
		vetoID := target.CommandData
		if err := h.db.LiftVeto(vetoID, "council-quorum"); err != nil {
			return mcp.NewToolResultError("failed to lift veto: " + err.Error()), nil
		}
		target.Status = "executed"
		h.db.SaveProposal(target)
		return mcp.NewToolResultText(fmt.Sprintf("Ethics veto %s lifted by council quorum.", vetoID)), nil // nosec

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

// ethicsVeto is the ethics-auditor equivalent of securityFix(): it intercepts a privileged
// action, but unlike security_fix (a proposal gating something not-yet-done), the veto itself
// takes effect *immediately* — it is a block already in force, not a patch awaiting approval.
// Only lifting it later goes through council_propose/council_vote/council_execute.
func (h *handler) ethicsVeto(_ context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	agent := ""
	if args, ok := req.Params.Arguments.(map[string]any); ok {
		if a, ok := args["_agent"].(string); ok {
			agent = a
		}
	}
	if agent != "ethics-auditor" {
		return mcp.NewToolResultError("ethics_veto rejected: only ethics-auditor may create a veto"), nil
	}

	planOrTaskRef, _ := req.RequireString("plan_or_task_ref")
	reason, _ := req.RequireString("reason")

	vetoID := fmt.Sprintf("VETO-%d", time.Now().UnixNano()%10000)
	proposalID := fmt.Sprintf("PROP-%d", time.Now().UnixNano()%10000)

	veto := &VetoRecord{
		ID:            vetoID,
		PlanOrTaskRef: planOrTaskRef,
		Status:        "active",
		CreatedBy:     agent,
		Reason:        reason,
		ProposalID:    proposalID,
		CreatedAt:     time.Now(),
	}
	if err := h.db.SaveVeto(veto); err != nil {
		return mcp.NewToolResultError("failed to record veto: " + err.Error()), nil
	}

	proposal := &CouncilProposal{
		ID:          proposalID,
		Title:       fmt.Sprintf("Lift ethics veto on %s", planOrTaskRef), // nosec
		Proposer:    agent,
		Votes:       0,
		Required:    3,
		Status:      "open",
		CreatedAt:   time.Now(),
		CommandType: "lift_ethics_veto",
		CommandData: vetoID,
	}
	if err := h.db.SaveProposal(proposal); err != nil {
		return mcp.NewToolResultError("veto recorded but failed to create lift-proposal: " + err.Error()), nil
	}

	return mcp.NewToolResultText(fmt.Sprintf(
		"Ethics veto %s on %q is now in effect. Lifting it requires council quorum (risk-manager, cto, security-auditor): Proposal %s.",
		vetoID, planOrTaskRef, proposalID,
	)), nil // nosec
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
