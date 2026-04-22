package api

import (
	"encoding/json"
	"net/http"
	"strings"

	"go-agent-llm-orchestrator/internal/db"
	"go-agent-llm-orchestrator/web"
)

type AdminServer struct {
	db *db.DB
}

func NewAdminServer(database *db.DB) *AdminServer {
	return &AdminServer{db: database}
}

func (s *AdminServer) Start(addr string) error {
	mux := http.NewServeMux()
	mux.HandleFunc("/api/v1/tasks", s.handleListTasks)
	mux.HandleFunc("/api/v1/tasks/", s.handleTaskAction)
	mux.HandleFunc("/api/v1/settings/telegram", s.handleSaveTelegramToken)
	mux.HandleFunc("/api/v1/settings/llm", s.handleSaveLLMSettings)
	mux.HandleFunc("/api/v1/audit", s.handleListAudit)
	mux.HandleFunc("/healthz", s.handleHealth)
	mux.HandleFunc("/readyz", s.handleHealth)
	
	// Serve static dashboard
	mux.Handle("/static/", http.FileServer(http.FS(web.StaticFiles)))
	mux.HandleFunc("/dashboard", func(w http.ResponseWriter, r *http.Request) {
		content, _ := web.StaticFiles.ReadFile("static/index.html")
		w.Header().Set("Content-Type", "text/html")
		w.Write(content)
	})
	
	// Metrics endpoint will be added here or via Prometheus registry
	
	return http.ListenAndServe(addr, mux)
}

func (s *AdminServer) handleListTasks(w http.ResponseWriter, r *http.Request) {
	// Dummy implementation for listing tasks from DB
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "ok", "message": "List of tasks"})
}

func (s *AdminServer) handleListAudit(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "ok", "message": "Audit logs"})
}

func (s *AdminServer) handleTaskAction(w http.ResponseWriter, r *http.Request) {
	parts := strings.Split(r.URL.Path, "/")
	if len(parts) < 5 {
		http.Error(w, "invalid path", http.StatusBadRequest)
		return
	}
	taskID := parts[4]
	action := parts[len(parts)-1]

	switch action {
	case "run":
		// Trigger run logic
	case "pause":
		status := "PAUSED"
		if r.Method == http.MethodDelete {
			status = "PENDING"
		}
		s.db.Exec("UPDATE tasks SET status = ? WHERE id = ?", status, taskID)
	}
	w.WriteHeader(http.StatusNoContent)
}

func (s *AdminServer) handleSaveTelegramToken(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var data struct {
		Token string `json:"token"`
	}
	json.NewDecoder(r.Body).Decode(&data)
	s.db.Exec("INSERT OR REPLACE INTO settings (key, value) VALUES ('telegram_token', ?)", data.Token)
	w.WriteHeader(http.StatusNoContent)
}

func (s *AdminServer) handleSaveLLMSettings(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var data struct {
		LocalModel  string `json:"local_model"`
		RemoteModel string `json:"remote_model"`
	}
	json.NewDecoder(r.Body).Decode(&data)
	if data.LocalModel != "" {
		s.db.Exec("INSERT OR REPLACE INTO settings (key, value) VALUES ('llm_local_model', ?)", data.LocalModel)
	}
	if data.RemoteModel != "" {
		s.db.Exec("INSERT OR REPLACE INTO settings (key, value) VALUES ('llm_remote_model', ?)", data.RemoteModel)
	}
	w.WriteHeader(http.StatusNoContent)
}

func (s *AdminServer) handleHealth(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusOK)
	w.Write([]byte("ok"))
}
