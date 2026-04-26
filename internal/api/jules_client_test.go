package api

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestJulesClient_GetStatus(t *testing.T) {
	// Mock server
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"id": "session-123", "state": "RUNNING"}`))
	}))
	defer server.Close()

	client := NewJulesClient(nil)
	client.BaseURL = server.URL
	client.APIKey = "mock-key"

	status, err := client.GetStatus(context.Background(), "session-123")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if status != "RUNNING" {
		t.Errorf("expected status RUNNING, got %s", status)
	}
}
