package api

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"go-agent-llm-orchestrator/internal/db"
)

type mockScheduler struct{}
func (m *mockScheduler) SyncTasks(ctx context.Context) error { return nil }
func (m *mockScheduler) TriggerTask(taskID string) {}

func TestAdminServer_handleListTasks(t *testing.T) {
	database, _ := db.InitDB(":memory:")
	server := NewAdminServer(database, &mockScheduler{}, nil, nil, nil)
	
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

func TestAdminServer_handleApproveTask(t *testing.T) {
	database, err := db.InitDB(":memory:")
	if err != nil {
		t.Fatal(err)
	}
	server := NewAdminServer(database, &mockScheduler{}, nil, nil, nil)
	
	if _, err := database.Exec("INSERT INTO tasks (id, name, schedule, status, pending_decision) VALUES ('task-1', 'test/repo', '@daily', 'WAITING', 'Proposed Plan')"); err != nil {
		t.Fatal(err)
	}
	
	body := `{"plan": "Edited Plan"}`
	req, _ := http.NewRequest("POST", "/api/v1/tasks/approve?id=task-1", strings.NewReader(body))
	rr := httptest.NewRecorder()
	
	server.handleApproveTask(rr, req)
	
	if rr.Code != http.StatusOK {
		t.Errorf("Expected status 200, got %d", rr.Code)
	}
	
	var status, decision string
	database.QueryRow("SELECT status, pending_decision FROM tasks WHERE id = 'task-1'").Scan(&status, &decision)
	if status != "PENDING" {
		t.Errorf("Expected status PENDING, got %s", status)
	}
	if decision != "Edited Plan" {
		t.Errorf("Expected plan to be updated, got %s", decision)
	}
}

func TestAdminServer_handleRejectTask(t *testing.T) {
	database, err := db.InitDB(":memory:")
	if err != nil {
		t.Fatal(err)
	}
	server := NewAdminServer(database, &mockScheduler{}, nil, nil, nil)
	
	if _, err := database.Exec("INSERT INTO tasks (id, name, schedule, status) VALUES ('task-2', 'test/repo', '@daily', 'WAITING')"); err != nil {
		t.Fatal(err)
	}
	
	body := `{"reason": "Too risky"}`
	req, _ := http.NewRequest("POST", "/api/v1/tasks/reject?id=task-2", strings.NewReader(body))
	rr := httptest.NewRecorder()
	
	server.handleRejectTask(rr, req)
	
	if rr.Code != http.StatusOK {
		t.Errorf("Expected status 200, got %d", rr.Code)
	}
	
	var status string
	database.QueryRow("SELECT status FROM tasks WHERE id = 'task-2'").Scan(&status)
	if status != "PAUSED" {
		t.Errorf("Expected status PAUSED, got %s", status)
	}
}
