package api

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestAdminServer_handleListTasks(t *testing.T) {
	server := NewAdminServer(nil, nil) // db/scheduler not used in this mock test
	
	req, err := http.NewRequest("GET", "/api/v1/tasks", nil)
	if err != nil {
		t.Fatal(err)
	}

	rr := httptest.NewRecorder()
	handler := http.HandlerFunc(server.listTasks)

	handler.ServeHTTP(rr, req)

	if status := rr.Code; status != http.StatusOK {
		t.Errorf("handler returned wrong status code: got %v want %v", status, http.StatusOK)
	}

	expected := `{"message":"List of tasks","status":"ok"}`
	if rr.Body.String() != expected+"\n" && rr.Body.String() != expected {
		t.Errorf("handler returned unexpected body: got %v want %v", rr.Body.String(), expected)
	}
}
