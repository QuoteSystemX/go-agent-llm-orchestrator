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

const defaultClassifyPrompt = `Classify the following task as either SIMPLE or COMPLEX.
SIMPLE: Short tasks, basic text processing, simple questions.
COMPLEX: Tasks involving code, large data volumes, multiple steps, or deep reasoning.

Task: %s

Respond with ONLY the word SIMPLE or COMPLEX.`

const defaultSupervisorPrompt = `Analyze this blocked session: %s. Task: %s. Provide a decision to unblock.`

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
	mux.HandleFunc("/api/v1/settings/llm", s.handleLLMSettings)
	mux.HandleFunc("/api/v1/settings/supervisor", s.handleSupervisorSettings)
	mux.HandleFunc("/api/v1/settings/prompts", s.handlePromptSettings)
	mux.HandleFunc("/api/v1/settings/prompt-library", s.handlePromptLibrarySettings)
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
	// Task IDs can contain slashes (e.g. "org/repo:agent:pattern"),
	// so we can't rely on parts[4] — extract everything after the prefix instead.
	const prefix = "/api/v1/tasks/"
	rest := strings.TrimPrefix(r.URL.Path, prefix)
	if rest == "" {
		http.Error(w, "invalid path", http.StatusBadRequest)
		return
	}

	// Sub-resource: /logs
	if strings.HasSuffix(rest, "/logs") {
		taskID := strings.TrimSuffix(rest, "/logs")
		s.listTaskLogs(w, r, taskID)
		return
	}

	// Actions: /run, /pause, /resume
	for _, action := range []string{"run", "pause", "resume"} {
		if strings.HasSuffix(rest, "/"+action) {
			taskID := strings.TrimSuffix(rest, "/"+action)
			s.handleTaskAction(w, r, taskID, action)
			return
		}
	}

	// Plain task CRUD
	taskID := rest
	switch r.Method {
	case http.MethodPut:
		s.updateTask(w, r, taskID)
	case http.MethodDelete:
		s.deleteTask(w, r, taskID)
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

func (s *AdminServer) getSetting(ctx context.Context, key, def string) string {
	var val string
	if err := s.db.QueryRowContext(ctx, "SELECT value FROM settings WHERE key = ?", key).Scan(&val); err != nil || val == "" {
		return def
	}
	return val
}

func (s *AdminServer) saveSetting(ctx context.Context, key, value string) error {
	_, err := s.db.ExecContext(ctx, "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", key, value)
	return err
}

func (s *AdminServer) handleLLMSettings(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{
			"local_model":   s.getSetting(r.Context(), "llm_local_model", ""),
			"remote_model":  s.getSetting(r.Context(), "llm_remote_model", ""),
			"jules_api_key": func() string {
				if s.getSetting(r.Context(), "jules_api_key", "") != "" {
					return "***"
				}
				return ""
			}(),
			"jules_base_url": s.getSetting(r.Context(), "jules_base_url", "https://jules.googleapis.com/v1alpha"),
		})
	case http.MethodPost:
		var data struct {
			LocalModel   string `json:"local_model"`
			RemoteModel  string `json:"remote_model"`
			JulesAPIKey  string `json:"jules_api_key"`
			JulesBaseURL string `json:"jules_base_url"`
		}
		json.NewDecoder(r.Body).Decode(&data)
		if data.LocalModel != "" {
			s.saveSetting(r.Context(), "llm_local_model", data.LocalModel)
		}
		if data.RemoteModel != "" {
			s.saveSetting(r.Context(), "llm_remote_model", data.RemoteModel)
		}
		if data.JulesAPIKey != "" {
			s.saveSetting(r.Context(), "jules_api_key", data.JulesAPIKey)
		}
		if data.JulesBaseURL != "" {
			s.saveSetting(r.Context(), "jules_base_url", data.JulesBaseURL)
		}
		w.WriteHeader(http.StatusNoContent)
	default:
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
	}
}

func (s *AdminServer) handleSupervisorSettings(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		raw := s.getSetting(r.Context(), "trigger_statuses", "AWAITING_USER_FEEDBACK,AWAITING_PLAN_APPROVAL")
		statuses := []string{}
		for _, p := range strings.Split(raw, ",") {
			if v := strings.TrimSpace(p); v != "" {
				statuses = append(statuses, v)
			}
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"trigger_statuses": statuses,
			"routing_simple":   s.getSetting(r.Context(), "routing_simple", "local"),
			"routing_complex":  s.getSetting(r.Context(), "routing_complex", "remote"),
		})
	case http.MethodPost:
		var data struct {
			TriggerStatuses []string `json:"trigger_statuses"`
			RoutingSimple   string   `json:"routing_simple"`
			RoutingComplex  string   `json:"routing_complex"`
		}
		if err := json.NewDecoder(r.Body).Decode(&data); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		if len(data.TriggerStatuses) > 0 {
			s.saveSetting(r.Context(), "trigger_statuses", strings.Join(data.TriggerStatuses, ","))
		}
		if data.RoutingSimple != "" {
			s.saveSetting(r.Context(), "routing_simple", data.RoutingSimple)
		}
		if data.RoutingComplex != "" {
			s.saveSetting(r.Context(), "routing_complex", data.RoutingComplex)
		}
		w.WriteHeader(http.StatusNoContent)
	default:
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
	}
}

func (s *AdminServer) handlePromptSettings(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{
			"classify":   s.getSetting(r.Context(), "prompt_classify", defaultClassifyPrompt),
			"supervisor": s.getSetting(r.Context(), "prompt_supervisor", defaultSupervisorPrompt),
		})
	case http.MethodPost:
		var data struct {
			Classify   string `json:"classify"`
			Supervisor string `json:"supervisor"`
		}
		if err := json.NewDecoder(r.Body).Decode(&data); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		if data.Classify != "" {
			s.saveSetting(r.Context(), "prompt_classify", data.Classify)
		}
		if data.Supervisor != "" {
			s.saveSetting(r.Context(), "prompt_supervisor", data.Supervisor)
		}
		w.WriteHeader(http.StatusNoContent)
	default:
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
	}
}

func (s *AdminServer) handlePromptLibrarySettings(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{
			"git_url":          s.getSetting(r.Context(), "prompt_library_git_url", ""),
			"git_branch":       s.getSetting(r.Context(), "prompt_library_git_branch", "main"),
			"cache_dir":        s.getSetting(r.Context(), "prompt_library_cache_dir", "/var/lib/orchestrator/prompt-lib"),
			"refresh_interval": s.getSetting(r.Context(), "prompt_library_refresh_interval", "1h"),
			// ssh_key is write-only: return masked indicator
			"ssh_key_set": func() string {
				if s.getSetting(r.Context(), "prompt_library_ssh_key", "") != "" {
					return "true"
				}
				return "false"
			}(),
		})
	case http.MethodPost:
		var data struct {
			GitURL          string `json:"git_url"`
			GitBranch       string `json:"git_branch"`
			CacheDir        string `json:"cache_dir"`
			RefreshInterval string `json:"refresh_interval"`
			SSHKey          string `json:"ssh_key"` // PEM content
		}
		if err := json.NewDecoder(r.Body).Decode(&data); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		if data.GitURL != "" {
			s.saveSetting(r.Context(), "prompt_library_git_url", data.GitURL)
		}
		if data.GitBranch != "" {
			s.saveSetting(r.Context(), "prompt_library_git_branch", data.GitBranch)
		}
		if data.CacheDir != "" {
			s.saveSetting(r.Context(), "prompt_library_cache_dir", data.CacheDir)
		}
		if data.RefreshInterval != "" {
			s.saveSetting(r.Context(), "prompt_library_refresh_interval", data.RefreshInterval)
		}
		if data.SSHKey != "" {
			s.saveSetting(r.Context(), "prompt_library_ssh_key", data.SSHKey)
		}
		w.WriteHeader(http.StatusNoContent)
	default:
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
	}
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

