package dto

import (
	"strings"
	"testing"

	"go-agent-llm-orchestrator/internal/db"
)

func TestAnalyzer_ParseProposals(t *testing.T) {
	a := &Analyzer{}
	
	response := `{"current_stage": "discovery", "progress": 10, "warnings": ["test warning"], "metadata": {"has_readme": "true"}, "proposals": [
		{"pattern": "discovery", "agent": "project-planner", "mission": "Analyze project", "reason": "Initial step"}
	]}`

	result, err := a.parseAnalysisResult(response)
	if err != nil {
		t.Fatalf("failed to parse: %v", err)
	}
	if len(result.Proposals) != 1 {
		t.Errorf("expected 1 proposal, got %d", len(result.Proposals))
	}
	if result.CurrentStage != "discovery" {
		t.Errorf("expected discovery stage, got %s", result.CurrentStage)
	}
	if len(result.Warnings) != 1 || result.Warnings[0] != "test warning" {
		t.Errorf("warnings not parsed correctly")
	}
	if result.Metadata["has_readme"] != "true" {
		t.Errorf("metadata not parsed correctly")
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
