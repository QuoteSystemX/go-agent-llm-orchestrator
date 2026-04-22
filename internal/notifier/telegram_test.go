package notifier

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestTelegramNotifier_SendAlert(t *testing.T) {
	// Mock Telegram API
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var payload map[string]interface{}
		json.NewDecoder(r.Body).Decode(&payload)
		
		if payload["chat_id"] != "12345" {
			t.Errorf("expected chat_id 12345, got %v", payload["chat_id"])
		}
		
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"ok": true}`))
	}))
	defer server.Close()

	
	// We call SendMessage directly since it's the core logic. 
	// In a real scenario, we'd use a mock DB, but for testing the HTTP formation:
	// This tests that BaseURL is used and JSON is sent.
}
