package dto

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
	"unicode/utf8"

	"go-agent-llm-orchestrator/internal/db"
)

func TestAnalyzer_IndexFile_UTF8(t *testing.T) {
	database, _ := db.InitDB(":memory:")
	a := NewAnalyzer(database, nil, nil, nil)
	
	tempDir, _ := os.MkdirTemp("", "rag-test")
	defer os.RemoveAll(tempDir)
	
	// Create a file with Russian characters at the boundary of 1000 characters
	// 999 'A's + 1 Russian 'Я' (2 bytes)
	content := strings.Repeat("A", 999) + "Я" + strings.Repeat("B", 1000)
	tmpFile := filepath.Join(tempDir, "test.txt")
	os.WriteFile(tmpFile, []byte(content), 0644)
	
	a.indexFile(tmpFile)
	
	// Check chunks in ragStore
	docs := a.ragStore.Search("Я", 10)
	if len(docs) == 0 {
		t.Fatal("expected to find chunk with 'Я'")
	}
	
	for _, doc := range docs {
		if !utf8.ValidString(doc.Content) {
			t.Errorf("invalid UTF-8 string found in chunk: %s", doc.Content)
		}
	}
}

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
	a := NewAnalyzer(database, nil, nil, nil)
	
	prompt := a.buildAnalysisPrompt("test-repo", "README content", "Wiki content", "Agent context", nil, nil, 1000)
	
	if !strings.Contains(prompt, "README content") {
		t.Error("prompt should contain README content")
	}
	if !strings.Contains(prompt, "Agent context") {
		t.Error("prompt should contain agent context")
	}
}

func TestAnalyzer_BuildPrompt_Truncation(t *testing.T) {
	database, _ := db.InitDB(":memory:")
	a := NewAnalyzer(database, nil, nil, nil)
	
	largeReadme := strings.Repeat("A", 5000)
	maxChars := 1000
	prompt := a.buildAnalysisPrompt("test-repo", largeReadme, "", "", nil, nil, maxChars)
	
	if len(prompt) > maxChars {
		t.Errorf("prompt exceeds maxChars: %d > %d", len(prompt), maxChars)
	}
	if !strings.Contains(prompt, "test-repo") {
		t.Error("prompt should still contain repository name")
	}
}
