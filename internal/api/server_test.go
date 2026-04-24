package api

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestAdminServer_handleListTasks(t *testing.T) {
	server := NewAdminServer(nil, nil, nil, nil) // db/scheduler/dto/analyzer not used in this mock test
	
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
