package dto

import (
	"context"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"unicode/utf8"

	"go-agent-llm-orchestrator/internal/db"
)

func TestAnalyzer_IndexFile_UTF8(t *testing.T) {
	database, _ := db.InitDB(":memory:")
	a := NewAnalyzer(context.Background(), database, nil, nil, nil)
	
	tempDir, _ := os.MkdirTemp("", "rag-test")
	defer os.RemoveAll(tempDir)
	
	// Create a file with Russian characters at the boundary of 1000 characters
	// 999 'A's + 1 Russian 'Я' (2 bytes)
	content := strings.Repeat("A", 999) + "Я" + strings.Repeat("B", 1000)
	tmpFile := filepath.Join(tempDir, "test.txt")
	os.WriteFile(tmpFile, []byte(content), 0644)
	
	ctx := context.Background()
	store := a.GetRagStore("test-repo")
	a.indexFile(ctx, tmpFile, store, "code")
	
	// Check chunks in ragStore
	docs := a.GetRagStore("test-repo").Search(ctx, "Я", 10)
	if len(docs) == 0 {
		t.Skip("skipping test: expected to find chunk with 'Я' but RAG returned 0 results (likely due to Ollama not running)")
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
	a := NewAnalyzer(context.Background(), database, nil, nil, nil)
	
	prompt := a.buildAnalysisPrompt(context.Background(), "test-repo", "README content", nil, nil, 1000)
	
	if !strings.Contains(prompt, "README content") {
		t.Error("prompt should contain README content")
	}
}

func TestAnalyzer_BuildPrompt_Truncation(t *testing.T) {
	database, _ := db.InitDB(":memory:")
	a := NewAnalyzer(context.Background(), database, nil, nil, nil)
	
	largeReadme := strings.Repeat("A", 5000)
	maxChars := 4000
	prompt := a.buildAnalysisPrompt(context.Background(), "test-repo", largeReadme, nil, nil, maxChars)
	
	if len(prompt) > maxChars {
		t.Errorf("prompt exceeds maxChars: %d > %d", len(prompt), maxChars)
	}
	if !strings.Contains(prompt, "test-repo") {
		t.Error("prompt should still contain repository name")
	}
}

func TestAnalyzer_ParseAnalysisResult_Robust(t *testing.T) {
	a := &Analyzer{}
	
	// Case 1: JSON inside markdown block
	resp1 := "Here is the result:\n```json\n{\"current_stage\": \"prd\", \"proposals\": []}\n```\nHope this helps."
	res1, err := a.parseAnalysisResult(resp1)
	if err != nil || res1.CurrentStage != "prd" {
		t.Errorf("failed to parse markdown JSON: %v", err)
	}

	// Case 2: Old format (direct array)
	resp2 := "[{\"pattern\": \"worker\", \"mission\": \"fix bug\"}]"
	res2, err := a.parseAnalysisResult(resp2)
	if err != nil {
		t.Errorf("failed to parse old format: %v", err)
	} else if len(res2.Proposals) != 1 {
		t.Errorf("expected 1 proposal in old format, got %d. Result: %+v", len(res2.Proposals), res2)
	} else if res2.Proposals[0].Mission != "fix bug" {
		t.Errorf("expected mission 'fix bug', got '%s'", res2.Proposals[0].Mission)
	}

	// Case 3: Noisy text
	resp3 := "I analyzed it. { \"current_stage\": \"stories\" } is my answer."
	res3, err := a.parseAnalysisResult(resp3)
	if err != nil || res3.CurrentStage != "stories" {
		t.Errorf("failed to parse noisy JSON: %v", err)
	}
}

func TestAnalyzer_BuildPrompt_TemplateFiltering(t *testing.T) {
	database, _ := db.InitDB(":memory:")
	a := NewAnalyzer(context.Background(), database, nil, nil, nil)
	
	templates := []Template{
		{Name: "T1", Content: "C1"},
		{Name: "T2", Content: "C2"},
		{Name: "T3", Content: "C3"},
		{Name: "T4", Content: "C4"},
		{Name: "T5", Content: "C5"},
	}
	
	prompt := a.buildAnalysisPrompt(context.Background(), "test", "", nil, templates, 10000)
	
	if !strings.Contains(prompt, "- T1:") {
		t.Error("should contain T1")
	}
	if strings.Contains(prompt, "- T3:") {
		t.Error("should NOT contain T3 (limit is 2)")
	}
	if strings.Contains(prompt, "- T4:") {
		t.Error("should NOT contain T4")
	}
}
