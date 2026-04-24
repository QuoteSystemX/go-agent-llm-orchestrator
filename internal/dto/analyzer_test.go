package dto

import (
	"strings"
	"testing"

	"go-agent-llm-orchestrator/internal/db"
)

func TestAnalyzer_ParseProposals(t *testing.T) {
	a := &Analyzer{}
	
	response := `Here are the proposals:
[
	{"pattern": "discovery", "agent": "project-planner", "mission": "Analyze project", "reason": "Initial step"}
]`

	proposals, err := a.parseProposals(response)
	if err != nil {
		t.Fatalf("failed to parse: %v", err)
	}
	if len(proposals) != 1 {
		t.Errorf("expected 1 proposal, got %d", len(proposals))
	}
	if proposals[0].Pattern != "discovery" {
		t.Errorf("expected discovery pattern, got %s", proposals[0].Pattern)
	}
}

func TestAnalyzer_BuildPrompt(t *testing.T) {
	database, _ := db.InitDB(":memory:")
	a := NewAnalyzer(database, nil, nil)
	
	prompt := a.buildAnalysisPrompt("test-repo", "README content", "Wiki content", "Agent context", nil, nil)
	
	if !strings.Contains(prompt, "README content") {
		t.Error("prompt should contain README content")
	}
	if !strings.Contains(prompt, "Agent context") {
		t.Error("prompt should contain agent context")
	}
}
