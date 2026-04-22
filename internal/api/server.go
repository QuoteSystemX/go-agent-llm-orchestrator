package api

import (
	"context"
	"encoding/json"
	"net/http"
	"strings"
	"time"

	"go-agent-llm-orchestrator/internal/db"
	"go-agent-llm-orchestrator/web"
	"github.com/robfig/cron/v3"
)

type Scheduler interface {
	SyncTasks(ctx context.Context) error
}

type AdminServer struct {
	db        *db.DB
	scheduler Scheduler
}

func NewAdminServer(database *db.DB, sched Scheduler) *AdminServer {
	return &AdminServer{
		db:        database,
		scheduler: sched,
	}
}

func (s *AdminServer) Start(addr string) error {
	mux := http.NewServeMux()
	
	// Tasks API
	mux.HandleFunc("/api/v1/tasks/next-runs", s.handleNextRuns)
	mux.HandleFunc("/api/v1/tasks", s.handleTasks)
	mux.HandleFunc("/api/v1/tasks/", s.handleTaskByID)
	
	// Settings & Audit
	mux.HandleFunc("/api/v1/settings/telegram", s.handleTelegramSettings)
	mux.HandleFunc("/api/v1/settings/llm", s.handleSaveLLMSettings)
	mux.HandleFunc("/api/v1/audit", s.handleListAudit)
	
	// Health
	mux.HandleFunc("/healthz", s.handleHealth)
	mux.HandleFunc("/readyz", s.handleHealth)
	
	// Root redirect/welcome
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/" {
			http.NotFound(w, r)
			return
		}
		w.Header().Set("Content-Type", "text/html")
		w.Write([]byte(`
			<!DOCTYPE html>
			<html>
			<head><title>Jules Orchestrator</title></head>
			<body style="font-family: sans-serif; text-align: center; padding-top: 50px; background: #0f172a; color: white;">
				<h1>Welcome to Jules Orchestrator 🤖</h1>
				<p>Your AI agents are under control.</p>
				<a href="/dashboard" style="display: inline-block; padding: 12px 24px; background: #3b82f6; color: white; text-decoration: none; border-radius: 8px; font-weight: bold; transition: background 0.3s;">Go to Dashboard</a>
				<br><br>
				<small style="color: #64748b;">API Version: v1</small>
			</body>
			</html>
		`))
	})
	
	// Serve static dashboard
	mux.Handle("/static/", http.FileServer(http.FS(web.StaticFiles)))
	mux.HandleFunc("/dashboard", func(w http.ResponseWriter, r *http.Request) {
		content, _ := web.StaticFiles.ReadFile("static/index.html")
		w.Header().Set("Content-Type", "text/html")
		w.Write(content)
	})
	
	return http.ListenAndServe(addr, mux)
}

type TaskResponse struct {
	ID         string    `json:"id"`
	Name       string    `json:"name"`
	Mission    string    `json:"mission"`
	Pattern    string    `json:"pattern"`
	Schedule   string    `json:"schedule"`
	Status     string    `json:"status"`
	LastRunAt  *time.Time `json:"last_run_at"`
	CreatedAt  time.Time `json:"created_at"`
}

func (s *AdminServer) handleTasks(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		s.listTasks(w, r)
	case http.MethodPost:
		s.createTask(w, r)
	default:
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
	}
}

func (s *AdminServer) listTasks(w http.ResponseWriter, r *http.Request) {
	rows, err := s.db.QueryContext(r.Context(), "SELECT id, name, mission, pattern, schedule, status, last_run_at, created_at FROM tasks ORDER BY created_at DESC")
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	var tasks []TaskResponse
	for rows.Next() {
		var t TaskResponse
		if err := rows.Scan(&t.ID, &t.Name, &t.Mission, &t.Pattern, &t.Schedule, &t.Status, &t.LastRunAt, &t.CreatedAt); err != nil {
			continue
		}
		tasks = append(tasks, t)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(tasks)
}

func (s *AdminServer) createTask(w http.ResponseWriter, r *http.Request) {
	var t TaskResponse
	if err := json.NewDecoder(r.Body).Decode(&t); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	
	if t.ID == "" {
		t.ID = strings.ToLower(strings.ReplaceAll(t.Name, " ", "-")) + "-" + time.Now().Format("05")
	}

	_, err := s.db.ExecContext(r.Context(), 
		"INSERT INTO tasks (id, name, mission, pattern, schedule, status) VALUES (?, ?, ?, ?, ?, ?)",
		t.ID, t.Name, t.Mission, t.Pattern, t.Schedule, "PENDING")
	
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	s.scheduler.SyncTasks(r.Context())
	w.WriteHeader(http.StatusCreated)
}

func (s *AdminServer) handleTaskByID(w http.ResponseWriter, r *http.Request) {
	parts := strings.Split(r.URL.Path, "/")
	if len(parts) < 5 {
		http.Error(w, "invalid path", http.StatusBadRequest)
		return
	}
	taskID := parts[4]

	// Handle sub-resources: /api/v1/tasks/:id/logs
	if len(parts) > 5 && parts[5] == "logs" {
		s.listTaskLogs(w, r, taskID)
		return
	}

	switch r.Method {
	case http.MethodPut:
		s.updateTask(w, r, taskID)
	case http.MethodDelete:
		s.deleteTask(w, r, taskID)
	case http.MethodPost: // Custom actions: /run, /pause
		action := parts[len(parts)-1]
		s.handleTaskAction(w, r, taskID, action)
	default:
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
	}
}

func (s *AdminServer) updateTask(w http.ResponseWriter, r *http.Request, id string) {
	var t TaskResponse
	if err := json.NewDecoder(r.Body).Decode(&t); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	_, err := s.db.ExecContext(r.Context(), 
		"UPDATE tasks SET name = ?, mission = ?, pattern = ?, schedule = ?, status = ? WHERE id = ?",
		t.Name, t.Mission, t.Pattern, t.Schedule, t.Status, id)
	
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	s.scheduler.SyncTasks(r.Context())
	w.WriteHeader(http.StatusNoContent)
}

func (s *AdminServer) deleteTask(w http.ResponseWriter, r *http.Request, id string) {
	_, err := s.db.ExecContext(r.Context(), "DELETE FROM tasks WHERE id = ?", id)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	s.scheduler.SyncTasks(r.Context())
	w.WriteHeader(http.StatusNoContent)
}

type LogResponse struct {
	ID         int       `json:"id"`
	ExecutedAt time.Time `json:"executed_at"`
	Input      string    `json:"input"`
	Output     string    `json:"output"`
	Status     string    `json:"status"`
	Error      string    `json:"error"`
	Duration   int       `json:"duration_ms"`
}

func (s *AdminServer) listTaskLogs(w http.ResponseWriter, r *http.Request, taskID string) {
	rows, err := s.db.QueryContext(r.Context(), "SELECT id, executed_at, input_data, output_data, status, error, duration_ms FROM task_logs WHERE task_id = ? ORDER BY executed_at DESC LIMIT 50", taskID)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	var logs []LogResponse
	for rows.Next() {
		var l LogResponse
		if err := rows.Scan(&l.ID, &l.ExecutedAt, &l.Input, &l.Output, &l.Status, &l.Error, &l.Duration); err != nil {
			continue
		}
		logs = append(logs, l)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(logs)
}

func (s *AdminServer) handleTaskAction(w http.ResponseWriter, r *http.Request, taskID, action string) {
	switch action {
	case "run":
		// Manual run could be implemented by adding to a high-priority queue
		w.WriteHeader(http.StatusAccepted)
	case "pause":
		s.db.ExecContext(r.Context(), "UPDATE tasks SET status = 'PAUSED' WHERE id = ?", taskID)
		s.scheduler.SyncTasks(r.Context())
		w.WriteHeader(http.StatusNoContent)
	case "resume":
		s.db.ExecContext(r.Context(), "UPDATE tasks SET status = 'PENDING' WHERE id = ?", taskID)
		s.scheduler.SyncTasks(r.Context())
		w.WriteHeader(http.StatusNoContent)
	default:
		http.Error(w, "unknown action", http.StatusBadRequest)
	}
}

func (s *AdminServer) handleListAudit(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "ok", "message": "Audit logs moved to task history"})
}

// handleTelegramSettings handles GET (get bot info) and POST (save token).
func (s *AdminServer) handleTelegramSettings(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodPost:
		var data struct {
			Token string `json:"token"`
		}
		json.NewDecoder(r.Body).Decode(&data)
		s.db.ExecContext(r.Context(), "INSERT OR REPLACE INTO settings (key, value) VALUES ('telegram_token', ?)", data.Token)
		w.WriteHeader(http.StatusNoContent)

	case http.MethodGet:
		row := s.db.QueryRowContext(r.Context(), "SELECT value FROM settings WHERE key = 'telegram_token'")
		var token string
		if err := row.Scan(&token); err != nil || token == "" {
			json.NewEncoder(w).Encode(map[string]string{"bot_name": "", "token": ""})
			return
		}
		// Call Telegram to resolve bot username
		resp, err := http.Get("https://api.telegram.org/bot" + token + "/getMe")
		if err != nil {
			http.Error(w, "telegram unreachable", http.StatusBadGateway)
			return
		}
		defer resp.Body.Close()
		var tgResp struct {
			Ok     bool `json:"ok"`
			Result struct {
				Username string `json:"username"`
			} `json:"result"`
		}
		json.NewDecoder(resp.Body).Decode(&tgResp)
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{"bot_name": tgResp.Result.Username, "token": "***"})

	default:
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
	}
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
		s.db.ExecContext(r.Context(), "INSERT OR REPLACE INTO settings (key, value) VALUES ('llm_local_model', ?)", data.LocalModel)
	}
	if data.RemoteModel != "" {
		s.db.ExecContext(r.Context(), "INSERT OR REPLACE INTO settings (key, value) VALUES ('llm_remote_model', ?)", data.RemoteModel)
	}
	w.WriteHeader(http.StatusNoContent)
}

func (s *AdminServer) handleHealth(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusOK)
	w.Write([]byte("ok"))
}

// handleNextRuns returns the next scheduled run time for each active task.
func (s *AdminServer) handleNextRuns(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	rows, err := s.db.QueryContext(r.Context(),
		`SELECT id, name, schedule, status FROM tasks WHERE status != 'PAUSED' ORDER BY name`)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	type NextRun struct {
		TaskID       string  `json:"task_id"`
		Name         string  `json:"name"`
		Schedule     string  `json:"schedule"`
		NextRun      string  `json:"next_run"`
		SecondsUntil float64 `json:"seconds_until"`
	}

	parser := cron.NewParser(cron.Minute | cron.Hour | cron.Dom | cron.Month | cron.Dow)
	now := time.Now()
	var results []NextRun

	for rows.Next() {
		var id, name, schedule, status string
		if err := rows.Scan(&id, &name, &schedule, &status); err != nil {
			continue
		}
		sched, err := parser.Parse(schedule)
		if err != nil {
			continue
		}
		next := sched.Next(now)
		results = append(results, NextRun{
			TaskID:       id,
			Name:         name,
			Schedule:     schedule,
			NextRun:      next.UTC().Format(time.RFC3339),
			SecondsUntil: next.Sub(now).Seconds(),
		})
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(results)
}

