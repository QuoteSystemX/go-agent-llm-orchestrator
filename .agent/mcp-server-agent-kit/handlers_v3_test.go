package main

import (
	"context"
	"testing"
	"time"

	"github.com/mark3labs/mcp-go/mcp"
)

func TestRBACEnforcement(t *testing.T) {
	db := newTestDB(t)
	h := &handler{db: db}
	ctx := context.Background()

	toolName := "workflows_list"
	agentName := "untrusted_agent"

	// 1. Initially allowed by default (default policy: allow if no record)
	req := mcp.CallToolRequest{}
	req.Params.Arguments = map[string]any{"_agent": agentName}
	
	// We need to wrap the handler with RBAC to test it
	// In main.go, this is done in main(), so we'll test the helper logic
	withRBAC := func(tool string, hdlr func(context.Context, mcp.CallToolRequest) (*mcp.CallToolResult, error)) func(context.Context, mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
			allowed, _ := h.db.CheckPermission(agentName, tool)
			if !allowed {
				return mcp.NewToolResultError("denied"), nil
			}
			return hdlr(ctx, req)
		}
	}

	rbacHandler := withRBAC(toolName, func(context.Context, mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		return mcp.NewToolResultText("ok"), nil
	})

	res, _ := rbacHandler(ctx, req)
	if res.IsError {
		t.Error("expected access to be allowed by default")
	}

	// 2. Explicitly deny
	h.db.SetPermission(agentName, toolName, false)
	res, _ = rbacHandler(ctx, req)
	if !res.IsError {
		t.Error("expected access to be denied after explicit restriction")
	}
}

func TestCouncilWorkflowBoundaries(t *testing.T) {
	db := newTestDB(t)
	h := &handler{db: db, projectRoot: "/tmp"}
	ctx := context.Background()

	// Create a proposal that is NOT approved
	pID := "PROP-FAIL"
	h.db.SaveProposal(&CouncilProposal{
		ID:       pID,
		Status:   "open",
		Votes:    1,
		Required: 2,
	})

	req := mcp.CallToolRequest{}
	req.Params.Arguments = map[string]any{"proposal_id": pID}
	
	res, err := h.executeProposal(ctx, req)
	if err != nil {
		t.Fatalf("executeProposal returned Go error: %v", err)
	}
	if !res.IsError {
		t.Error("expected error when executing unapproved proposal")
	}
}

func TestSecretsEdgeCases(t *testing.T) {
	db := newTestDB(t)
	h := &handler{db: db}
	ctx := context.Background()

	// 1. Missing secret
	req := mcp.CallToolRequest{}
	req.Params.Arguments = map[string]any{"key": "nonexistent"}
	res, _ := h.getSecret(ctx, req)
	if !res.IsError {
		t.Error("expected tool error for missing secret")
	}

	// 2. Overwrite secret
	h.db.SetSecret("key1", "val1")
	h.db.SetSecret("key1", "val2")
	val, _ := h.db.GetSecret("key1")
	if val != "val2" {
		t.Errorf("expected val2, got %s", val)
	}
}

func TestMetricsRecording(t *testing.T) {
	db := newTestDB(t)
	h := &handler{db: db}
	
	// Add a dummy metric
	err := h.db.RecordMetric("test_tool", "test_agent", "default", 150*time.Millisecond, true)
	if err != nil {
		t.Fatalf("RecordMetric failed: %v", err)
	}

	ctx := context.Background()
	res, err := h.getMetrics(ctx, mcp.CallToolRequest{})
	if err != nil {
		t.Fatalf("getMetrics failed: %v", err)
	}
	if res.IsError {
		t.Fatalf("getMetrics tool error: %v", res.Content)
	}
}

func TestCouncilVoteRequiresIdentity(t *testing.T) {
	db := newTestDB(t)
	h := &handler{db: db, projectRoot: "/tmp"}
	ctx := context.Background()

	pID := "PROP-NOID"
	h.db.SaveProposal(&CouncilProposal{ID: pID, Status: "open", Required: 2})

	req := mcp.CallToolRequest{}
	req.Params.Arguments = map[string]any{"id": pID} // no _agent
	res, err := h.voteProposal(ctx, req)
	if err != nil {
		t.Fatalf("voteProposal returned Go error: %v", err)
	}
	if !res.IsError {
		t.Error("expected vote without _agent identity to be rejected")
	}
}

func TestCouncilVoteRejectsDuplicateVoter(t *testing.T) {
	db := newTestDB(t)
	h := &handler{db: db, projectRoot: "/tmp"}
	ctx := context.Background()

	pID := "PROP-DUPE"
	h.db.SaveProposal(&CouncilProposal{ID: pID, Status: "open", Required: 3})

	vote := func(agent string) *mcp.CallToolResult {
		req := mcp.CallToolRequest{}
		req.Params.Arguments = map[string]any{"id": pID, "_agent": agent}
		res, err := h.voteProposal(ctx, req)
		if err != nil {
			t.Fatalf("voteProposal returned Go error: %v", err)
		}
		return res
	}

	vote("risk-manager")
	vote("risk-manager") // same voter calling twice must not double-count

	ps, err := h.db.GetProposals()
	if err != nil {
		t.Fatalf("GetProposals failed: %v", err)
	}
	var p *CouncilProposal
	for _, cand := range ps {
		if cand.ID == pID {
			p = cand
		}
	}
	if p == nil {
		t.Fatal("proposal not found after voting")
	}
	if p.Votes != 1 {
		t.Errorf("expected votes=1 after same agent voted twice, got %d", p.Votes)
	}
	if len(p.Voters) != 1 || p.Voters[0] != "risk-manager" {
		t.Errorf("expected voters=[risk-manager], got %v", p.Voters)
	}

	// A second, distinct voter must be counted and persisted correctly.
	vote("quality-security-lead")
	ps, _ = h.db.GetProposals()
	for _, cand := range ps {
		if cand.ID == pID {
			p = cand
		}
	}
	if p.Votes != 2 {
		t.Errorf("expected votes=2 after a distinct second voter, got %d", p.Votes)
	}
	if p.Status == "approved" {
		t.Error("proposal should still be open at 2/3 votes")
	}

	vote("cto")
	ps, _ = h.db.GetProposals()
	for _, cand := range ps {
		if cand.ID == pID {
			p = cand
		}
	}
	if p.Status != "approved" {
		t.Errorf("expected status=approved at 3/3 votes, got %s", p.Status)
	}
}

// TestCouncilProposalVotersPersistRoundTrip exercises SaveProposal/GetProposals
// directly (bypassing the MCP handler) to confirm the Voters field actually
// survives a write + reload through the real Postgres column, not just
// in-memory during a single voteProposal call.
func TestCouncilProposalVotersPersistRoundTrip(t *testing.T) {
	db := newTestDB(t)

	pID := "PROP-ROUNDTRIP"
	err := db.SaveProposal(&CouncilProposal{
		ID:       pID,
		Title:    "Round-trip test",
		Status:   "open",
		Votes:    2,
		Voters:   []string{"risk-manager", "quality-security-lead"},
		Required: 3,
	})
	if err != nil {
		t.Fatalf("SaveProposal failed: %v", err)
	}

	ps, err := db.GetProposals()
	if err != nil {
		t.Fatalf("GetProposals failed: %v", err)
	}
	var p *CouncilProposal
	for _, cand := range ps {
		if cand.ID == pID {
			p = cand
		}
	}
	if p == nil {
		t.Fatal("proposal not found after save")
	}
	if len(p.Voters) != 2 || p.Voters[0] != "risk-manager" || p.Voters[1] != "quality-security-lead" {
		t.Errorf("expected voters=[risk-manager quality-security-lead] after reload, got %v", p.Voters)
	}
}

// TestCouncilProposalLegacyRowWithoutVoters simulates a row written before
// the voters column existed (a genuine NULL, not the '[]' default new rows
// get) — GetProposals must tolerate this rather than erroring on scan or
// panicking on json.Unmarshal of a nil pointer.
func TestCouncilProposalLegacyRowWithoutVoters(t *testing.T) {
	db := newTestDB(t)

	_, err := db.conn.Exec(
		`INSERT INTO proposals (id, title, proposer, votes, required, status, created_at, command_type, command_data, voters)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NULL)`,
		"PROP-LEGACY", "Pre-migration row", "orchestrator", 1, 3, "open", time.Now(), "", "",
	)
	if err != nil {
		t.Fatalf("failed to insert legacy row: %v", err)
	}

	ps, err := db.GetProposals()
	if err != nil {
		t.Fatalf("GetProposals failed on legacy NULL voters row: %v", err)
	}
	var p *CouncilProposal
	for _, cand := range ps {
		if cand.ID == "PROP-LEGACY" {
			p = cand
		}
	}
	if p == nil {
		t.Fatal("legacy proposal not found")
	}
	if len(p.Voters) != 0 {
		t.Errorf("expected empty Voters for a legacy NULL row, got %v", p.Voters)
	}
}

// TestSecurityFixVoteExecuteEndToEnd walks the full gated path an AI agent's
// security_fix call actually takes: intercepted into a proposal, voted on by
// two distinct agents (duplicate vote from the first agent must not count
// twice), then executed once quorum (2, per securityFix's own Required) is
// reached. This is the scenario handlers_gov.go's securityFix()/executeProposal()
// exist for — TestCouncilWorkflowBoundaries only covers the unapproved-rejection
// path, not the full approve-then-execute one.
func TestSecurityFixVoteExecuteEndToEnd(t *testing.T) {
	db := newTestDB(t)
	dispatcher := NewDispatcher(db, 1) // not Started — we only need Submit's DB write, not a live worker
	h := &handler{db: db, dispatcher: dispatcher, projectRoot: "/tmp"}
	ctx := context.Background()

	// 1. Agent calls security_fix — gets intercepted into a proposal.
	fixReq := mcp.CallToolRequest{}
	fixReq.Params.Arguments = map[string]any{
		"vulnerability_id": "CVE-TEST-1",
		"file_path":        "internal/auth/token.go",
		"_agent":           "security-auditor",
	}
	fixRes, err := h.securityFix(ctx, fixReq)
	if err != nil {
		t.Fatalf("securityFix returned Go error: %v", err)
	}
	if fixRes.IsError {
		t.Fatalf("securityFix tool error: %v", fixRes.Content)
	}

	ps, err := h.db.GetProposals()
	if err != nil {
		t.Fatalf("GetProposals failed: %v", err)
	}
	var proposal *CouncilProposal
	for _, cand := range ps {
		if cand.CommandType == "security_fix" && cand.CommandData == "CVE-TEST-1|internal/auth/token.go" {
			proposal = cand
		}
	}
	if proposal == nil {
		t.Fatal("securityFix did not create the expected proposal")
	}
	if proposal.Required != 2 {
		t.Errorf("expected security_fix proposals to require 2 votes, got %d", proposal.Required)
	}

	vote := func(agent string) *mcp.CallToolResult {
		req := mcp.CallToolRequest{}
		req.Params.Arguments = map[string]any{"id": proposal.ID, "_agent": agent}
		res, err := h.voteProposal(ctx, req)
		if err != nil {
			t.Fatalf("voteProposal returned Go error: %v", err)
		}
		return res
	}

	// 2. First voter votes twice — must not inflate the count past 1.
	vote("risk-manager")
	vote("risk-manager")

	// 3. Still below quorum — execute must refuse.
	execReq := mcp.CallToolRequest{}
	execReq.Params.Arguments = map[string]any{"id": proposal.ID}
	execRes, err := h.executeProposal(ctx, execReq)
	if err != nil {
		t.Fatalf("executeProposal returned Go error: %v", err)
	}
	if !execRes.IsError {
		t.Error("expected executeProposal to refuse at 1/2 votes")
	}

	// 4. Second, distinct voter reaches quorum.
	vote("quality-security-lead")

	ps, _ = h.db.GetProposals()
	for _, cand := range ps {
		if cand.ID == proposal.ID {
			proposal = cand
		}
	}
	if proposal.Status != "approved" {
		t.Fatalf("expected status=approved at 2/2 distinct votes, got %s", proposal.Status)
	}

	// 5. Now execute should succeed and flip status to "executed".
	execRes, err = h.executeProposal(ctx, execReq)
	if err != nil {
		t.Fatalf("executeProposal returned Go error: %v", err)
	}
	if execRes.IsError {
		t.Fatalf("executeProposal tool error after approval: %v", execRes.Content)
	}

	ps, _ = h.db.GetProposals()
	for _, cand := range ps {
		if cand.ID == proposal.ID {
			proposal = cand
		}
	}
	if proposal.Status != "executed" {
		t.Errorf("expected status=executed after executeProposal, got %s", proposal.Status)
	}
}
