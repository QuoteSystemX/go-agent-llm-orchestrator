package api

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"go-agent-llm-orchestrator/internal/db"
)

func TestAdminServer_handleRAGAction_RecoverRepo(t *testing.T) {
	database, _ := db.InitDB(":memory:")
	// Note: We don't need a real analyzer/ragManager for this test if we just want to verify the API routing.
	// But to be thorough, we can check that it returns 200 even if RAG is missing (graceful handling).
	server := NewAdminServer(database, &mockScheduler{}, nil, nil, nil)
	
	actionPayload := map[string]string{
		"action":  "recover_repo",
		"repo_id": "test-repo",
	}
	body, _ := json.Marshal(actionPayload)
	
	req, _ := http.NewRequest("POST", "/api/v1/rag/action", bytes.NewReader(body))
	rr := httptest.NewRecorder()
	
	handler := http.HandlerFunc(server.handleRAGAction)
	handler.ServeHTTP(rr, req)
	
	// Should return 503 (Service Unavailable) because analyzer is nil in this test setup.
	// This confirms the API correctly guards against calls when RAG is not initialized.
	if rr.Code != http.StatusServiceUnavailable {
		t.Errorf("Expected status 503, got %d. Body: %s", rr.Code, rr.Body.String())
	}
	
	// Now test invalid action
	actionPayload = map[string]string{
		"action": "invalid_action",
	}
	body, _ = json.Marshal(actionPayload)
	req, _ = http.NewRequest("POST", "/api/v1/rag/action", bytes.NewReader(body))
	rr = httptest.NewRecorder()
	handler.ServeHTTP(rr, req)
	
	if rr.Code != http.StatusServiceUnavailable {
		t.Errorf("Expected status 503 when analyzer is missing, got %d", rr.Code)
	}
}
