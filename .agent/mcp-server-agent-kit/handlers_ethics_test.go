package main

import (
	"context"
	"testing"

	"github.com/mark3labs/mcp-go/mcp"
)

// TestEthicsVetoFullLifecycle covers the end-to-end flow the ethics-council design specifies:
// ethics-auditor vetoes (takes effect immediately, not gated on a vote) -> its own vote on
// lifting is rejected (the deadlock cto's review found) -> an unrelated agent's vote is rejected
// (closed pool, not open to anyone with council_vote permission) -> risk-manager/cto/
// security-auditor vote -> council_execute lifts the veto.
func TestEthicsVetoFullLifecycle(t *testing.T) {
	db := newTestDB(t)
	h := &handler{db: db, projectRoot: "/tmp"}
	ctx := context.Background()

	vetoReq := mcp.CallToolRequest{}
	vetoReq.Params.Arguments = map[string]any{
		"plan_or_task_ref": "PLAN-42",
		"reason":           "unreviewed prod DB write",
		"_agent":           "ethics-auditor",
	}
	vetoRes, err := h.ethicsVeto(ctx, vetoReq)
	if err != nil {
		t.Fatalf("ethicsVeto returned Go error: %v", err)
	}
	if vetoRes.IsError {
		t.Fatalf("ethicsVeto tool error: %v", vetoRes.Content)
	}

	ps, err := h.db.GetProposals()
	if err != nil {
		t.Fatalf("GetProposals failed: %v", err)
	}
	var proposal *CouncilProposal
	for _, cand := range ps {
		if cand.CommandType == "lift_ethics_veto" {
			proposal = cand
		}
	}
	if proposal == nil {
		t.Fatal("ethicsVeto did not create the expected lift_ethics_veto proposal")
	}
	if proposal.Required != 3 {
		t.Errorf("expected lift_ethics_veto proposals to require 3 votes, got %d", proposal.Required)
	}

	veto, err := h.db.GetVeto(proposal.CommandData)
	if err != nil {
		t.Fatalf("GetVeto failed: %v", err)
	}
	// The veto itself is a block already in force — it must be "active" immediately, not
	// waiting on the proposal's votes.
	if veto.Status != "active" {
		t.Fatalf("expected veto to be active immediately on creation, got %s", veto.Status)
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

	// ethics-auditor cannot vote to lift a veto it created — this is the deadlock cto's
	// review found: excluding it must not silently work by using a lower threshold, it must
	// be an outright rejection of that specific voter.
	if res := vote("ethics-auditor"); !res.IsError {
		t.Error("expected ethics-auditor's vote on its own veto's lift to be rejected")
	}

	// An unrelated identity is not part of the closed lift-quorum pool either.
	if res := vote("random-agent"); !res.IsError {
		t.Error("expected an unrelated agent's vote on a lift_ethics_veto proposal to be rejected")
	}

	// Re-fetch: none of the rejected votes should have been counted.
	ps, _ = h.db.GetProposals()
	for _, cand := range ps {
		if cand.ID == proposal.ID {
			proposal = cand
		}
	}
	if proposal.Votes != 0 {
		t.Fatalf("expected 0 votes after only rejected attempts, got %d", proposal.Votes)
	}

	// The real 3-role quorum votes.
	vote("risk-manager")
	vote("cto")
	vote("security-auditor")

	ps, _ = h.db.GetProposals()
	for _, cand := range ps {
		if cand.ID == proposal.ID {
			proposal = cand
		}
	}
	if proposal.Status != "approved" {
		t.Fatalf("expected status=approved at 3/3 quorum votes, got %s", proposal.Status)
	}

	execReq := mcp.CallToolRequest{}
	execReq.Params.Arguments = map[string]any{"id": proposal.ID}
	execRes, err := h.executeProposal(ctx, execReq)
	if err != nil {
		t.Fatalf("executeProposal returned Go error: %v", err)
	}
	if execRes.IsError {
		t.Fatalf("executeProposal tool error after approval: %v", execRes.Content)
	}

	veto, err = h.db.GetVeto(veto.ID)
	if err != nil {
		t.Fatalf("GetVeto failed after lift: %v", err)
	}
	if veto.Status != "lifted" {
		t.Errorf("expected veto status=lifted after executeProposal, got %s", veto.Status)
	}
	if veto.LiftedBy == "" {
		t.Error("expected LiftedBy to be recorded")
	}
}

// TestEthicsVetoRejectsNonAuditorCreator ensures ethics_veto can't be called by an arbitrary
// identity — only ethics-auditor may declare a veto.
func TestEthicsVetoRejectsNonAuditorCreator(t *testing.T) {
	db := newTestDB(t)
	h := &handler{db: db, projectRoot: "/tmp"}
	ctx := context.Background()

	req := mcp.CallToolRequest{}
	req.Params.Arguments = map[string]any{
		"plan_or_task_ref": "PLAN-1",
		"reason":           "trying to impersonate ethics-auditor",
		"_agent":           "not-ethics-auditor",
	}
	res, err := h.ethicsVeto(ctx, req)
	if err != nil {
		t.Fatalf("ethicsVeto returned Go error: %v", err)
	}
	if !res.IsError {
		t.Error("expected ethics_veto to reject a caller that isn't ethics-auditor")
	}

	ps, err := h.db.GetProposals()
	if err != nil {
		t.Fatalf("GetProposals failed: %v", err)
	}
	for _, p := range ps {
		if p.CommandType == "lift_ethics_veto" {
			t.Error("no lift_ethics_veto proposal should have been created for a rejected veto")
		}
	}
}

// TestLiftVetoRace covers the specific race-condition concern two independent reviewers raised
// during this ticket's design deliberation: two lift attempts for the same veto must not both
// "succeed" — the second must fail cleanly.
func TestLiftVetoRace(t *testing.T) {
	db := newTestDB(t)
	h := &handler{db: db, projectRoot: "/tmp"}
	ctx := context.Background()

	vetoReq := mcp.CallToolRequest{}
	vetoReq.Params.Arguments = map[string]any{
		"plan_or_task_ref": "PLAN-99",
		"reason":           "race test",
		"_agent":           "ethics-auditor",
	}
	if _, err := h.ethicsVeto(ctx, vetoReq); err != nil {
		t.Fatalf("ethicsVeto returned Go error: %v", err)
	}
	ps, _ := h.db.GetProposals()
	var vetoID string
	for _, p := range ps {
		if p.CommandType == "lift_ethics_veto" {
			vetoID = p.CommandData
		}
	}
	if vetoID == "" {
		t.Fatal("no veto ID found")
	}

	if err := h.db.LiftVeto(vetoID, "first-caller"); err != nil {
		t.Fatalf("first LiftVeto should succeed, got: %v", err)
	}
	if err := h.db.LiftVeto(vetoID, "second-caller"); err == nil {
		t.Error("second LiftVeto on an already-lifted veto should fail, got nil error")
	}

	veto, err := h.db.GetVeto(vetoID)
	if err != nil {
		t.Fatalf("GetVeto failed: %v", err)
	}
	if veto.LiftedBy != "first-caller" {
		t.Errorf("expected LiftedBy to remain 'first-caller' (first writer wins), got %q", veto.LiftedBy)
	}
}
