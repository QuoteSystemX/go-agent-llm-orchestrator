package api

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"testing"

	"go-agent-llm-orchestrator/internal/db"
	"go-agent-llm-orchestrator/internal/dto"
)

func TestAdminServer_handleRAGSearch(t *testing.T) {
	// Setup temporary DB and paths
	tempDir, err := os.MkdirTemp("", "rag_test")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(tempDir)

	database, err := db.InitDB(":memory:")
	if err != nil {
		t.Fatal(err)
	}
	
	// Create Analyzer
	analyzer := dto.NewAnalyzer(context.Background(), database, nil, nil, nil)
	server := NewAdminServer(database, &mockScheduler{}, nil, analyzer, nil)
	
	// 1. Test empty search (no repos indexed)
	reqBody := map[string]any{
		"query": "test query",
		"top_k": 5,
	}
	body, _ := json.Marshal(reqBody)
	
	req, _ := http.NewRequest("POST", "/api/v1/rag/search", bytes.NewBuffer(body))
	rr := httptest.NewRecorder()
	
	server.handleRAGSearch(rr, req)
	
	if rr.Code != http.StatusOK {
		t.Errorf("Expected status 200, got %d", rr.Code)
	}
	
	var results []any
	if err := json.NewDecoder(rr.Body).Decode(&results); err != nil {
		t.Fatalf("Failed to decode response: %v", err)
	}
	
	if len(results) != 0 {
		t.Errorf("Expected 0 results, got %d", len(results))
	}

	// 2. Test invalid payload
	req, _ = http.NewRequest("POST", "/api/v1/rag/search", bytes.NewBufferString("invalid json"))
	rr = httptest.NewRecorder()
	server.handleRAGSearch(rr, req)
	if rr.Code != http.StatusBadRequest {
		t.Errorf("Expected status 400 for invalid payload, got %d", rr.Code)
	}

	// 3. Test missing query
	body, _ = json.Marshal(map[string]any{"top_k": 5})
	req, _ = http.NewRequest("POST", "/api/v1/rag/search", bytes.NewBuffer(body))
	rr = httptest.NewRecorder()
	server.handleRAGSearch(rr, req)
	if rr.Code != http.StatusBadRequest {
		t.Errorf("Expected status 400 for missing query, got %d", rr.Code)
	}
}
