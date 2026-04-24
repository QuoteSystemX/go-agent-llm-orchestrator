package api

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"runtime"
	"sort"
	"strings"
	"time"

	"go-agent-llm-orchestrator/internal/db"
	"go-agent-llm-orchestrator/internal/dto"
	"go-agent-llm-orchestrator/internal/llm"
	"go-agent-llm-orchestrator/internal/monitor"
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
	TriggerTask(taskID string)
}

type GitSyncer interface {
	Sync(ctx context.Context) error
}

type PromptChecker interface {
	HasPrompt(agent, pattern, mission string) bool
}

type AdminServer struct {
	db              *db.DB
	scheduler       Scheduler
	statsAggregator *monitor.StatsAggregator
	gitSyncer       GitSyncer
	promptChecker   PromptChecker
	healthMonitor   *monitor.HealthMonitor
	logBuf          *LogBuffer
	dtoMgr          *dto.TemplateManager
	analyzer        *dto.Analyzer
	startTime       time.Time
}

func NewAdminServer(database *db.DB, sched Scheduler, dtoMgr *dto.TemplateManager, analyzer *dto.Analyzer, aggregator *monitor.StatsAggregator) *AdminServer {
	return &AdminServer{
		db:              database,
		scheduler:       sched,
		dtoMgr:          dtoMgr,
		analyzer:        analyzer,
		statsAggregator: aggregator,
		startTime:       time.Now(),
	}
}

// SetLogBuffer attaches an in-memory log buffer so /api/v1/logs can serve it.
func (s *AdminServer) SetLogBuffer(lb *LogBuffer) { s.logBuf = lb }

// SetGitSyncer attaches a git syncer so saving SSH key triggers an immediate sync.
func (s *AdminServer) SetGitSyncer(gs GitSyncer) { s.gitSyncer = gs }

// SetPromptChecker attaches a prompt checker so tasks can report whether their prompt file exists.
func (s *AdminServer) SetPromptChecker(pc PromptChecker) { s.promptChecker = pc }

// SetHealthMonitor attaches a health monitor to track system component status.
func (s *AdminServer) SetHealthMonitor(hm *monitor.HealthMonitor) { s.healthMonitor = hm }

// maskSecret returns the first 4 and last 4 characters of a secret with "..." in between.
// Short secrets are fully masked.
func maskSecret(v string) string {
	if v == "" {
		return ""
	}
	if len(v) <= 8 {
		return "***"
	}
	return v[:4] + "..." + v[len(v)-4:]
}

// effectiveKey returns the key from DB first, then falls back to the env variable.
// Second return value is the source: "db", "env", or "".
func (s *AdminServer) effectiveKey(ctx context.Context, dbKey, envKey string) (string, string) {
	if val := s.getSetting(ctx, dbKey, ""); val != "" {
		return val, "db"
	}
	if val := os.Getenv(envKey); val != "" {
		return val, "env"
	}
	return "", ""
}

func (s *AdminServer) Start(addr string) error {
	mux := http.NewServeMux()
	
	// Tasks API
	mux.HandleFunc("/api/v1/tasks/next-runs", s.handleNextRuns)
	mux.HandleFunc("/api/v1/tasks", s.handleTasks)
	mux.HandleFunc("/api/v1/tasks/", s.handleTaskByID)
	mux.HandleFunc("/api/v1/tasks/approve", s.handleApproveTask)
	mux.HandleFunc("/api/v1/tasks/reject", s.handleRejectTask)

	// Settings & Audit
	mux.HandleFunc("/api/v1/settings/telegram", s.handleTelegramSettings)
	mux.HandleFunc("/api/v1/settings/llm", s.handleLLMSettings)
	mux.HandleFunc("/api/v1/settings/supervisor", s.handleSupervisorSettings)
	mux.HandleFunc("/api/v1/settings/prompts", s.handlePromptSettings)
	mux.HandleFunc("/api/v1/tasks/run", s.handleRunTask)
	mux.HandleFunc("/api/v1/settings/prompt-library", s.handlePromptLibrarySettings)
	mux.HandleFunc("/api/v1/settings/prompt-library/sync", s.handlePromptLibrarySync)
	mux.HandleFunc("/api/v1/audit", s.handleListAudit)
	mux.HandleFunc("/api/v1/audit/logs", s.handleListAuditLogs)
	mux.HandleFunc("/api/v1/audit/logs/details", s.handleGetTaskRunDetails)
	mux.HandleFunc("/api/v1/chat", s.handleChat)
	mux.HandleFunc("/api/v1/chat/stream", s.handleChatStream)
	mux.HandleFunc("/api/v1/chat/history", s.handleGetChatHistory)
	mux.HandleFunc("/api/v1/health", s.handleHealth)
	mux.HandleFunc("/api/v1/system/settings", s.handleSystemSettings)
	mux.HandleFunc("/api/v1/system/usage", s.handleSystemUsage)
	mux.HandleFunc("/api/v1/system/stats", s.handleSystemStats)

	// DTO Templates API
	mux.HandleFunc("/api/v1/dto/templates", s.handleTemplates)
	mux.HandleFunc("/api/v1/dto/templates/", s.handleTemplateByID)
	mux.HandleFunc("/api/v1/dto/analyze", s.handleAnalyze)

	// Logs
	mux.HandleFunc("/api/v1/logs", s.handleLogs)
	
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
	ID          string     `json:"id"`
	Name        string     `json:"name"`
	Agent       string     `json:"agent"`
	Mission     string     `json:"mission"`
	Pattern     string     `json:"pattern"`
	Schedule    string     `json:"schedule"`
	Status      string     `json:"status"`
	PromptReady bool       `json:"prompt_ready"`
	Importance  int        `json:"importance"`
	Category    string     `json:"category"`
	LastRunAt   *time.Time `json:"last_run_at"`
	CreatedAt   time.Time  `json:"created_at"`
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
	rows, err := s.db.QueryContext(r.Context(),
		"SELECT id, name, COALESCE(agent,''), mission, pattern, schedule, status, importance, category, last_run_at, created_at FROM tasks ORDER BY created_at DESC")
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	var tasks []TaskResponse
	for rows.Next() {
		var t TaskResponse
		if err := rows.Scan(&t.ID, &t.Name, &t.Agent, &t.Mission, &t.Pattern, &t.Schedule, &t.Status, &t.Importance, &t.Category, &t.LastRunAt, &t.CreatedAt); err != nil {
			continue
		}
		tasks = append(tasks, t)
	}
	rows.Close() // Close rows immediately to release the DB connection

	// Enrich tasks with prompt status outside of the DB iteration
	for i := range tasks {
		if s.promptChecker != nil {
			tasks[i].PromptReady = s.promptChecker.HasPrompt(tasks[i].Agent, tasks[i].Pattern, tasks[i].Mission)
		} else {
			tasks[i].PromptReady = true
		}
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
		"INSERT INTO tasks (id, name, mission, pattern, schedule, status, importance, category) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
		t.ID, t.Name, t.Mission, t.Pattern, t.Schedule, "PENDING", t.Importance, t.Category)
	
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
		"UPDATE tasks SET name = ?, mission = ?, pattern = ?, schedule = ?, status = ?, importance = ?, category = ? WHERE id = ?",
		t.Name, t.Mission, t.Pattern, t.Schedule, t.Status, t.Importance, t.Category, id)
	
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
	rows, err := s.db.History().QueryContext(r.Context(), "SELECT id, executed_at, input_data, output_data, status, error, duration_ms FROM task_logs WHERE task_id = ? ORDER BY executed_at DESC LIMIT 50", taskID)
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

func (s *AdminServer) handleLogs(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	if s.logBuf == nil {
		json.NewEncoder(w).Encode([]LogEntry{})
		return
	}
	json.NewEncoder(w).Encode(s.logBuf.Entries())
}

func (s *AdminServer) handleLLMSettings(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		julesKey, julesKeySource := s.effectiveKey(r.Context(), "jules_api_key", "JULES_API_KEY")
		masked := maskSecret(julesKey)
		if masked != "" {
			masked = "[" + julesKeySource + "] " + masked
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{
			"local_model":             s.getSetting(r.Context(), "llm_local_model", ""),
			"remote_model":            s.getSetting(r.Context(), "llm_remote_model", ""),
			"jules_api_key":           masked,
			"jules_base_url":          s.getSetting(r.Context(), "jules_base_url", "https://jules.googleapis.com/v1alpha"),
			"local_context_window":    s.getSetting(r.Context(), "llm_local_context_window", "4096"),
			"local_temperature":       s.getSetting(r.Context(), "llm_local_temperature", "0.7"),
			"system_prompt":           s.getSetting(r.Context(), "llm_system_prompt", "You are a professional coding assistant and project orchestrator."),
		})
	case http.MethodPost:
		var data struct {
			LocalModel         string `json:"local_model"`
			RemoteModel        string `json:"remote_model"`
			JulesAPIKey        string `json:"jules_api_key"`
			JulesBaseURL       string `json:"jules_base_url"`
			LocalContextWindow string `json:"local_context_window"`
			LocalTemperature   string `json:"local_temperature"`
			SystemPrompt       string `json:"system_prompt"`
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
		if data.LocalContextWindow != "" {
			s.saveSetting(r.Context(), "llm_local_context_window", data.LocalContextWindow)
		}
		if data.LocalTemperature != "" {
			s.saveSetting(r.Context(), "llm_local_temperature", data.LocalTemperature)
		}
		if data.SystemPrompt != "" {
			s.saveSetting(r.Context(), "llm_system_prompt", data.SystemPrompt)
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
		pat, patSource := s.effectiveKey(r.Context(), "prompt_library_pat", "PROMPT_LIBRARY_PAT")

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{
			"git_url":          s.db.GetSetting("prompt_library_git_url", ""),
			"git_branch":       s.db.GetSetting("prompt_library_git_branch", "main"),
			"cache_dir":        s.db.GetSetting("prompt_library_cache_dir", "/var/lib/orchestrator/prompt-lib"),
			"refresh_interval": s.db.GetSetting("prompt_library_refresh_interval", "1h"),
			"patterns_path":    s.db.GetSetting("prompt_library_patterns_path", "prompt/patterns"),
			"agents_path":      s.db.GetSetting("prompt_library_agents_path", ".agent/agents"),
			"workflows_path":   s.db.GetSetting("prompt_library_workflows_path", ".agent/workflows"),
			"pat_set": func() string {
				if pat != "" {
					return "true (" + patSource + ")"
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
			PatternsPath    string `json:"patterns_path"`
			AgentsPath      string `json:"agents_path"`
			WorkflowsPath   string `json:"workflows_path"`
			PAT             string `json:"pat"` // GitHub token
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
		if data.PatternsPath != "" {
			s.saveSetting(r.Context(), "prompt_library_patterns_path", data.PatternsPath)
		}
		if data.AgentsPath != "" {
			s.saveSetting(r.Context(), "prompt_library_agents_path", data.AgentsPath)
		}
		if data.WorkflowsPath != "" {
			s.saveSetting(r.Context(), "prompt_library_workflows_path", data.WorkflowsPath)
		}
		if data.PAT != "" {
			s.saveSetting(r.Context(), "prompt_library_pat", data.PAT)
			// Trigger immediate sync so auto-paused tasks resume without waiting for the interval.
			if s.gitSyncer != nil {
				go s.gitSyncer.Sync(context.Background())
			}
		}
		w.WriteHeader(http.StatusNoContent)
	default:
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
	}
}

// handlePromptLibrarySync triggers an immediate git sync of the prompt library.
func (s *AdminServer) handlePromptLibrarySync(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	if s.gitSyncer == nil {
		http.Error(w, "git syncer not available", http.StatusServiceUnavailable)
		return
	}
	go s.gitSyncer.Sync(context.Background())
	w.WriteHeader(http.StatusAccepted)
}

// handleNextRuns returns the next scheduled run time for each active task.
func (s *AdminServer) handleNextRuns(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	rows, err := s.db.Main().QueryContext(r.Context(),
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

	sort.Slice(results, func(i, j int) bool {
		return results[i].SecondsUntil < results[j].SecondsUntil
	})
	
	// Keep 5 as requested by user
	if len(results) > 5 {
		results = results[:5]
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(results)
}

func (s *AdminServer) handleChat(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req struct {
		Messages []map[string]string `json:"messages"`
		Provider string              `json:"provider"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	if len(req.Messages) == 0 {
		http.Error(w, "messages are required", http.StatusBadRequest)
		return
	}

	// Use SIMPLE classification for chat by default (as it's a "lite" chat)
	router := llm.NewRouter(s.db)
	response, err := router.GenerateChat(r.Context(), llm.Simple, req.Messages, req.Provider)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"response": response})
}

func (s *AdminServer) handleChatStream(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req struct {
		Messages []map[string]string `json:"messages"`
		Provider string              `json:"provider"`
		Repo     string              `json:"repo"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	if len(req.Messages) == 0 {
		http.Error(w, "messages are required", http.StatusBadRequest)
		return
	}

	// Save user message (last one)
	userMsg := req.Messages[len(req.Messages)-1]["content"]
	log.Printf("Chat: Received message for repo '%s' (Provider: %s): %s", req.Repo, req.Provider, userMsg)
	s.db.SaveChatMessage(r.Context(), "user", userMsg, req.Provider, req.Repo)

	// If a repository is selected, use RAG to enhance the context
	if req.Repo != "" && s.analyzer != nil {
		context := s.analyzer.SearchContext(userMsg, 3)
		if context != "" {
			ragMsg := map[string]string{
				"role":    "system",
				"content": fmt.Sprintf("Use the following context from repository '%s' to answer the question:\n%s", req.Repo, context),
			}
			// Prepend RAG context to help the model
			req.Messages = append([]map[string]string{ragMsg}, req.Messages...)
		}
	}

	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("Transfer-Encoding", "chunked")

	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "streaming not supported", http.StatusInternalServerError)
		return
	}

	router := llm.NewRouter(s.db)
	tokens, err := router.GenerateChatStream(r.Context(), llm.Simple, req.Messages, req.Provider)
	if err != nil {
		log.Printf("Chat: Stream error: %v", err)
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	var fullResponse strings.Builder
	for token := range tokens {
		fullResponse.WriteString(token)
		fmt.Fprintf(w, "data: %s\n\n", token)
		flusher.Flush()
	}

	// Save assistant response
	if fullResponse.Len() > 0 {
		log.Printf("Chat: Assistant responded with %d characters", fullResponse.Len())
		s.db.SaveChatMessage(r.Context(), "assistant", fullResponse.String(), req.Provider, req.Repo)
	}

	fmt.Fprintf(w, "data: [DONE]\n\n")
	flusher.Flush()
}

func (s *AdminServer) handleGetTaskRunDetails(w http.ResponseWriter, r *http.Request) {
	logIDStr := r.URL.Query().Get("log_id")
	var logID int64
	fmt.Sscanf(logIDStr, "%d", &logID)
	
	details, err := s.db.GetTaskRunDetails(r.Context(), logID)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(details)
}

func (s *AdminServer) handleGetChatHistory(w http.ResponseWriter, r *http.Request) {
	repo := r.URL.Query().Get("repo")
	history, err := s.db.GetChatHistory(r.Context(), repo, 50)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(history)
}

func (s *AdminServer) handleHealth(w http.ResponseWriter, r *http.Request) {
	if s.healthMonitor == nil {
		http.Error(w, "health monitor not initialized", http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(s.healthMonitor.GetStatus())
}

func (s *AdminServer) handleRunTask(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	taskID := r.URL.Query().Get("id")
	if taskID == "" {
		http.Error(w, "missing task id", http.StatusBadRequest)
		return
	}
	s.scheduler.TriggerTask(taskID)
	w.WriteHeader(http.StatusAccepted)
}

func (s *AdminServer) handleApproveTask(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	taskID := r.URL.Query().Get("id")
	var req struct {
		Plan string `json:"plan"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	_, err := s.db.ExecContext(r.Context(), "UPDATE tasks SET status = 'PENDING', pending_decision = ? WHERE id = ?", req.Plan, taskID)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	s.scheduler.TriggerTask(taskID)
	w.WriteHeader(http.StatusOK)
}

func (s *AdminServer) handleRejectTask(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	taskID := r.URL.Query().Get("id")
	_, err := s.db.ExecContext(r.Context(), "UPDATE tasks SET status = 'PAUSED', pending_decision = '' WHERE id = ?", taskID)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	w.WriteHeader(http.StatusOK)
}

func (s *AdminServer) handleListAuditLogs(w http.ResponseWriter, r *http.Request) {
	hoursStr := r.URL.Query().Get("hours")
	hours := 24
	if hoursStr != "" {
		fmt.Sscanf(hoursStr, "%d", &hours)
	}

	// 1. Fetch all tasks to a map for joining in Go (cross-DB JOIN not possible)
	taskRows, err := s.db.Main().QueryContext(r.Context(), "SELECT id, name, agent, mission FROM tasks")
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	defer taskRows.Close()
	taskMap := make(map[string]struct {
		Name    string
		Agent   string
		Mission string
	})
	for taskRows.Next() {
		var id, name, agent, mission string
		if err := taskRows.Scan(&id, &name, &agent, &mission); err == nil {
			taskMap[id] = struct {
				Name    string
				Agent   string
				Mission string
			}{name, agent, mission}
		}
	}

	// 2. Query logs from History DB
	rows, err := s.db.History().QueryContext(r.Context(), `
		SELECT id, task_id, session_id, executed_at, status, error, duration_ms
		FROM task_logs
		WHERE executed_at > datetime('now', '-' || ? || ' hours')
		ORDER BY executed_at DESC
	`, hours)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	var logs []map[string]any
	for rows.Next() {
		var id int
		var taskID, sessionID, executedAt, status, errorMsg string
		var duration int
		if err := rows.Scan(&id, &taskID, &sessionID, &executedAt, &status, &errorMsg, &duration); err != nil {
			continue
		}

		tInfo := taskMap[taskID]
		logs = append(logs, map[string]any{
			"id":          id,
			"task_id":      taskID,
			"session_id":   sessionID,
			"executed_at":  executedAt,
			"status":       status,
			"error":        errorMsg,
			"duration_ms":  duration,
			"repo_name":    tInfo.Name,
			"agent":        tInfo.Agent,
			"mission":      tInfo.Mission,
		})
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(logs)
}

func (s *AdminServer) handleSystemStats(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var m runtime.MemStats
	runtime.ReadMemStats(&m)

	// Simple CPU usage approximation for macOS/Linux using /proc/loadavg or sysctl
	// Since we are on Mac, we can try to use a command if needed, or just return memory for now.
	// We'll provide Memory in MB.
	cpuHist, memHist, taskHist := s.statsAggregator.GetHistory()

	stats := map[string]any{
		"num_goroutine":    runtime.NumGoroutine(),
		"memory_alloc_mb":  m.Alloc / 1024 / 1024,
		"memory_sys_mb":    m.Sys / 1024 / 1024,
		"uptime_seconds":   int(time.Since(s.startTime).Seconds()),
		"num_cpu":          runtime.NumCPU(),
		"last_gc_pause_ms": m.PauseNs[(m.NumGC+255)%256] / 1000000,
		"history": map[string]any{
			"cpu":    cpuHist,
			"memory": memHist,
			"tasks":  taskHist,
		},
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(stats)
}

func (s *AdminServer) handleSystemSettings(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		limit, _ := s.db.GetDailyLimit(r.Context())
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]any{
			"daily_task_limit": limit,
		})
	case http.MethodPost:
		var data struct {
			DailyTaskLimit int `json:"daily_task_limit"`
		}
		if err := json.NewDecoder(r.Body).Decode(&data); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		s.db.SetSetting("daily_task_limit", fmt.Sprintf("%d", data.DailyTaskLimit))
		w.WriteHeader(http.StatusNoContent)
	default:
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
	}
}

func (s *AdminServer) handleSystemUsage(w http.ResponseWriter, r *http.Request) {
	usage, err := s.db.GetDailyUsage(r.Context())
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	limit, _ := s.db.GetDailyLimit(r.Context())
	upcoming, _ := s.db.GetUpcomingTaskCountToday(r.Context())

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]any{
		"usage":    usage,
		"limit":    limit,
		"forecast": usage + upcoming,
	})
}

func (s *AdminServer) handleTemplates(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		templates, err := s.dtoMgr.ListTemplates(r.Context())
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		json.NewEncoder(w).Encode(templates)
	case http.MethodPost:
		var t dto.Template
		if err := json.NewDecoder(r.Body).Decode(&t); err != nil {
			http.Error(w, "invalid payload", http.StatusBadRequest)
			return
		}
		if t.Name == "" || t.Content == "" {
			http.Error(w, "name and content are required", http.StatusBadRequest)
			return
		}
		if err := s.dtoMgr.SaveTemplate(r.Context(), t.Name, t.Content); err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		w.WriteHeader(http.StatusCreated)
	default:
		w.WriteHeader(http.StatusMethodNotAllowed)
	}
}

func (s *AdminServer) handleTemplateByID(w http.ResponseWriter, r *http.Request) {
	name := strings.TrimPrefix(r.URL.Path, "/api/v1/dto/templates/")
	if name == "" {
		http.Error(w, "missing template name", http.StatusBadRequest)
		return
	}

	switch r.Method {
	case http.MethodGet:
		t, err := s.dtoMgr.GetTemplate(r.Context(), name)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		if t == nil {
			http.NotFound(w, r)
			return
		}
		json.NewEncoder(w).Encode(t)
	case http.MethodDelete:
		if err := s.dtoMgr.DeleteTemplate(r.Context(), name); err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		w.WriteHeader(http.StatusNoContent)
	default:
		w.WriteHeader(http.StatusMethodNotAllowed)
	}
}

func (s *AdminServer) handleAnalyze(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	repoName := r.URL.Query().Get("repo")
	if repoName == "" {
		http.Error(w, "missing repo parameter", http.StatusBadRequest)
		return
	}

	proposals, err := s.analyzer.AnalyzeRepo(r.Context(), repoName)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	json.NewEncoder(w).Encode(proposals)
}
