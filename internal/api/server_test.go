package api

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"go-agent-llm-orchestrator/internal/db"
)

func TestAdminServer_handleListTasks(t *testing.T) {
	database, _ := db.InitDB(":memory:")
	server := NewAdminServer(database, nil, nil, nil, nil)
	
	req, err := http.NewRequest("GET", "/api/v1/tasks", nil)
	if err != nil {
		t.Fatal(err)
	}

	rr := httptest.NewRecorder()
	handler := http.HandlerFunc(server.handleTasks)

	handler.ServeHTTP(rr, req)

	if status := rr.Code; status != http.StatusOK {
		t.Errorf("handler returned wrong status code: got %v want %v", status, http.StatusOK)
	}
}
