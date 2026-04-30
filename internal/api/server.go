package api

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"runtime"
	"sort"
	"strings"
	"time"

	"go-agent-llm-orchestrator/internal/budget"
	"go-agent-llm-orchestrator/internal/db"
	"go-agent-llm-orchestrator/internal/dto"
	"go-agent-llm-orchestrator/internal/llm"
	"go-agent-llm-orchestrator/internal/monitor"
	"go-agent-llm-orchestrator/internal/traffic"
	"go-agent-llm-orchestrator/internal/rag"
	"go-agent-llm-orchestrator/web"
	"github.com/gorilla/websocket"
	"github.com/robfig/cron/v3"
)

const defaultClassifyPrompt = `Classify the following task as either SIMPLE or COMPLEX.
SIMPLE: Short tasks, basic text processing, simple questions.
COMPLEX: Tasks involving code, large data volumes, multiple steps, or deep reasoning.

Task: %s

Respond with ONLY the word SIMPLE or COMPLEX.`

const defaultSupervisorPrompt = `Analyze this blocked session: %s. Task: %s. Provide a decision to unblock.`

type Scheduler interface {
	NotifyTaskChange(taskID string)
	NotifyAllTasksChange()
	RemoveTaskFromScheduler(taskID string)
	TriggerTask(taskID string)
	PauseTaskLoop(ctx context.Context, taskID string) error
	ForceTaskSuccess(ctx context.Context, taskID string) error
}

type GitSyncer interface {
	Sync(ctx context.Context) error
}

type JulesDeleter interface {
	DeleteSession(ctx context.Context, sessionID string) error
}

type PromptChecker interface {
	HasPrompt(agent, pattern, mission string) bool
}

type AdminServer struct {
	db              *db.DB
	scheduler       Scheduler
	julesDeleter    JulesDeleter
	statsAggregator *monitor.StatsAggregator
	gitSyncer       GitSyncer
	promptChecker   PromptChecker
	healthMonitor   *monitor.HealthMonitor
	logBuf          *LogBuffer
	dtoMgr          *dto.TemplateManager
	analyzer        *dto.Analyzer
	hub             *Hub
	budgetMgr       *budget.Manager
	driftDetector   *monitor.DriftDetector
	trafficManager  *traffic.TrafficManager
	webhookBus      chan<- monitor.WebhookEvent
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

// SetHub attaches a websocket hub.
func (s *AdminServer) SetHub(h *Hub) { s.hub = h }

// SetWebhookBus attaches the event bus for webhooks.
func (s *AdminServer) SetWebhookBus(bus chan<- monitor.WebhookEvent) { s.webhookBus = bus }
func (s *AdminServer) SetJulesDeleter(jd JulesDeleter)               { s.julesDeleter = jd }

// SetBudgetManager attaches a budget manager.
func (s *AdminServer) SetBudgetManager(bm *budget.Manager) { s.budgetMgr = bm }

// SetDriftDetector attaches a drift detector.
func (s *AdminServer) SetDriftDetector(dd *monitor.DriftDetector) { s.driftDetector = dd }

// SetTrafficManager attaches a traffic manager.
func (s *AdminServer) SetTrafficManager(tm *traffic.TrafficManager) { s.trafficManager = tm }

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
	mux.HandleFunc("/api/v1/tasks/pause-loop", s.handlePauseTaskLoop)
	mux.HandleFunc("/api/v1/tasks/force-success", s.handleForceTaskSuccess)

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
	mux.HandleFunc("/api/v1/chat/history", s.handleChatHistory)
	mux.HandleFunc("/api/v1/health", s.handleHealth)
	mux.HandleFunc("/api/v1/system/settings", s.handleSystemSettings)
	mux.HandleFunc("/api/v1/system/usage", s.handleSystemUsage)
	mux.HandleFunc("/api/v1/system/stats", s.handleSystemStats)
	mux.HandleFunc("/api/v1/system/drift", s.handleDriftStatus)
	mux.HandleFunc("/api/v1/system/traffic", s.handleTrafficStatus)

	// DTO API
	mux.HandleFunc("/api/v1/dto/templates", s.handleTemplates)
	mux.HandleFunc("/api/v1/dto/templates/", s.handleTemplateByID)
	mux.HandleFunc("/api/v1/dto/analyze", s.handleAnalyze)
	mux.HandleFunc("/api/v1/dto/status", s.handleDTOStatus)
	mux.HandleFunc("/api/v1/dto/chat", s.handleDTOChat)
	mux.HandleFunc("/api/v1/dto/session", s.handleDTOSession)
	mux.HandleFunc("/api/v1/dto/session/clear", s.handleDTOClearSession)
	mux.HandleFunc("/api/v1/dto/finalize", s.handleDTOFinalize)
	
	// RAG API
	mux.HandleFunc("/api/v1/rag/stats", s.handleRAGStats)
	mux.HandleFunc("/api/v1/rag/action", s.handleRAGAction)
	mux.HandleFunc("/api/v1/rag/search", s.handleRAGSearch)

	// Budgets API
	mux.HandleFunc("/api/v1/budgets", s.handleBudgets)

	// Webhooks
	mux.HandleFunc("/api/v1/webhooks/jules", s.handleJulesWebhook)

	// Logs
	mux.HandleFunc("/api/v1/logs", s.handleLogs)
	mux.HandleFunc("/api/v1/ws", s.handleWS)
	
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
	ID            string     `json:"id"`
	Name          string     `json:"name"`
	Agent         string     `json:"agent"`
	Mission       string     `json:"mission"`
	Pattern       string     `json:"pattern"`
	Schedule      string     `json:"schedule"`
	Status        string     `json:"status"`
	PromptReady   bool       `json:"prompt_ready"`
	Importance    int        `json:"importance"`
	Category      string     `json:"category"`
	LastRunAt     *time.Time `json:"last_run_at"`
	CreatedAt     time.Time  `json:"created_at"`
	FailureCount  int        `json:"failure_count"`
	LastError     string     `json:"last_error"`
	JulesTasks    int        `json:"jules_tasks"`
	LastSessionID string     `json:"last_session_id"`
	MaxRetries    int        `json:"max_retries"`
	CurrentRetry  int        `json:"current_retry"`
	HasDrift      bool       `json:"has_drift"`
	RAGStatus       string     `json:"rag_status"`
	RAGMode         string     `json:"rag_mode"`
	RAGFilesIndexed int        `json:"rag_files_indexed"`
	RAGTotalFiles   int        `json:"rag_total_files"`
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
	// Fetch Jules session counts per task repository (name)
	julesCounts := map[string]int{}
	countRows, err := s.db.Main().QueryContext(r.Context(), `
		SELECT t.name, COUNT(s.id) 
		FROM tasks t
		JOIN sessions s ON t.id = s.task_id
		WHERE s.jules_session_id != ''
		GROUP BY t.name`)
	if err == nil {
		defer countRows.Close()
		for countRows.Next() {
			var name string
			var count int
			if countRows.Scan(&name, &count) == nil {
				julesCounts[name] = count
			}
		}
	}

	rows, err := s.db.QueryContext(r.Context(),
		`SELECT id, name, COALESCE(agent,''), mission, pattern, schedule, status, importance, category, last_run_at, created_at, failure_count,
		        COALESCE((SELECT jules_session_id FROM sessions WHERE task_id = tasks.id ORDER BY updated_at DESC LIMIT 1), '') as last_session_id,
		        COALESCE(last_error, ''), max_retries, current_retry
		 FROM tasks ORDER BY created_at DESC`)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	tasks := []TaskResponse{}
	for rows.Next() {
		var t TaskResponse
		if err := rows.Scan(&t.ID, &t.Name, &t.Agent, &t.Mission, &t.Pattern, &t.Schedule, &t.Status, &t.Importance, &t.Category, &t.LastRunAt, &t.CreatedAt, &t.FailureCount, &t.LastSessionID, &t.LastError, &t.MaxRetries, &t.CurrentRetry); err != nil {
			continue
		}
		t.JulesTasks = julesCounts[t.Name]
		tasks = append(tasks, t)
	}
	rows.Close() // Close rows immediately to release the DB connection

	// Fetch last error per task from the history DB (separate SQLite file).
	lastErrors := map[string]string{}
	errRows, err := s.db.History().QueryContext(r.Context(), `
		SELECT task_id, error FROM task_logs
		WHERE id IN (
			SELECT MAX(id) FROM task_logs
			WHERE error IS NOT NULL AND error != ''
			GROUP BY task_id
		)`)
	if err == nil {
		defer errRows.Close()
		for errRows.Next() {
			var taskID, errMsg string
			if errRows.Scan(&taskID, &errMsg) == nil {
				lastErrors[taskID] = errMsg
			}
		}
	}

	// Enrich tasks with prompt status, last error, and RAG status outside of the DB iteration
	for i := range tasks {
		if s.promptChecker != nil {
			tasks[i].PromptReady = s.promptChecker.HasPrompt(tasks[i].Agent, tasks[i].Pattern, tasks[i].Mission)
		} else {
			tasks[i].PromptReady = true
		}
		tasks[i].LastError = lastErrors[tasks[i].ID]

		// RAG health info
		if s.analyzer != nil && s.analyzer.GetRagManager() != nil {
			if store := s.analyzer.GetRagManager().GetStore(tasks[i].Name); store != nil {
				stats := store.GetStats()
				tasks[i].RAGStatus = stats.Status
				tasks[i].RAGMode = stats.StorageMode
				tasks[i].RAGFilesIndexed = stats.FilesIndexed
				tasks[i].RAGTotalFiles = stats.TotalFiles
			}
		}
	}

	// Enrich with drift info
	driftResults := map[string]bool{}
	if s.driftDetector != nil {
		for _, d := range s.driftDetector.GetLastResults() {
			driftResults[d.RepoName] = d.HasDrift
		}
	}
	for i := range tasks {
		tasks[i].HasDrift = driftResults[tasks[i].Name]
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

	s.scheduler.NotifyTaskChange(t.ID)
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

	s.scheduler.NotifyTaskChange(id)
	w.WriteHeader(http.StatusNoContent)
}

func (s *AdminServer) deleteTask(w http.ResponseWriter, r *http.Request, id string) {
	// Cancel all Jules sessions associated with this task before removing it locally.
	if s.julesDeleter != nil {
		rows, err := s.db.QueryContext(r.Context(), "SELECT jules_session_id FROM sessions WHERE task_id = ? AND jules_session_id != ''", id)
		if err == nil {
			defer rows.Close()
			for rows.Next() {
				var sessionID string
				if rows.Scan(&sessionID) == nil && sessionID != "" {
					if err := s.julesDeleter.DeleteSession(r.Context(), sessionID); err != nil {
						log.Printf("deleteTask: Jules session %s delete failed (ignoring): %v", sessionID, err)
					}
				}
			}
		}
	}

	_, err := s.db.ExecContext(r.Context(), "DELETE FROM tasks WHERE id = ?", id)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	s.scheduler.RemoveTaskFromScheduler(id)
	w.WriteHeader(http.StatusNoContent)
}

func (s *AdminServer) handlePauseTaskLoop(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var req struct {
		TaskID string `json:"task_id"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	if err := s.scheduler.PauseTaskLoop(r.Context(), req.TaskID); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

func (s *AdminServer) handleForceTaskSuccess(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var req struct {
		TaskID string `json:"task_id"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	if err := s.scheduler.ForceTaskSuccess(r.Context(), req.TaskID); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
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
	limit := 50
	offset := 0
	if l := r.URL.Query().Get("limit"); l != "" {
		fmt.Sscanf(l, "%d", &limit)
	}
	if o := r.URL.Query().Get("offset"); o != "" {
		fmt.Sscanf(o, "%d", &offset)
	}

	rows, err := s.db.History().QueryContext(r.Context(), "SELECT id, executed_at, input_data, output_data, status, error, duration_ms FROM task_logs WHERE task_id = ? ORDER BY executed_at DESC LIMIT ? OFFSET ?", taskID, limit, offset)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	logs := []LogResponse{}
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
		// Protect service tasks from manual pause
		var pattern string
		if err := s.db.QueryRowContext(r.Context(), "SELECT pattern FROM tasks WHERE id = ?", taskID).Scan(&pattern); err != nil {
			log.Printf("pauseTask: failed to look up pattern for task %s: %v", taskID, err)
		}
		servicePatterns := []string{"discovery", "story_writer", "sprint_planner", "full_cycle", "sprint_closer"}
		for _, p := range servicePatterns {
			if p == pattern {
				http.Error(w, "Core service tasks cannot be paused", http.StatusForbidden)
				return
			}
		}

		if _, err := s.db.ExecContext(r.Context(), "UPDATE tasks SET status = 'PAUSED' WHERE id = ?", taskID); err != nil {
			http.Error(w, "failed to pause task: "+err.Error(), http.StatusInternalServerError)
			return
		}
		s.scheduler.NotifyTaskChange(taskID)
		w.WriteHeader(http.StatusNoContent)
	case "resume":
		if _, err := s.db.ExecContext(r.Context(), "UPDATE tasks SET status = 'PENDING' WHERE id = ?", taskID); err != nil {
			http.Error(w, "failed to resume task: "+err.Error(), http.StatusInternalServerError)
			return
		}
		s.scheduler.NotifyTaskChange(taskID)
		w.WriteHeader(http.StatusNoContent)
	default:
		http.Error(w, "unknown action", http.StatusBadRequest)
	}
}

func (s *AdminServer) handleListAudit(w http.ResponseWriter, r *http.Request) {
	limitStr := r.URL.Query().Get("limit")
	offsetStr := r.URL.Query().Get("offset")
	hoursStr := r.URL.Query().Get("hours")

	limit := 50
	offset := 0
	hours := 0 // 0 means all time

	if limitStr != "" { fmt.Sscanf(limitStr, "%d", &limit) }
	if offsetStr != "" { fmt.Sscanf(offsetStr, "%d", &offset) }
	if hoursStr != "" { fmt.Sscanf(hoursStr, "%d", &hours) }

	query := "SELECT id, session_id, action, details, created_at FROM audit_logs "
	args := []any{}

	if hours > 0 {
		query += "WHERE created_at > datetime('now', '-' || ? || ' hours') "
		args = append(args, hours)
	}

	query += "ORDER BY created_at DESC LIMIT ? OFFSET ?"
	args = append(args, limit, offset)

	rows, err := s.db.History().QueryContext(r.Context(), query, args...)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	logs := []map[string]any{}
	for rows.Next() {
		var id int
		var sessionID, action, details, createdAt string
		if err := rows.Scan(&id, &sessionID, &action, &details, &createdAt); err == nil {
			logs = append(logs, map[string]any{
				"id":         id,
				"session_id": sessionID,
				"action":     action,
				"details":    details,
				"created_at": createdAt,
			})
		}
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(logs)
}

func (s *AdminServer) handleTrafficStatus(w http.ResponseWriter, r *http.Request) {
	if s.trafficManager == nil {
		http.Error(w, "Traffic Manager not initialized", http.StatusServiceUnavailable)
		return
	}
	queue := s.trafficManager.GetQueue()
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]any{
		"queue": queue,
	})
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

func (s *AdminServer) handleWS(w http.ResponseWriter, r *http.Request) {
	if s.hub == nil {
		http.Error(w, "websocket hub not initialized", http.StatusServiceUnavailable)
		return
	}

	upgrader := websocket.Upgrader{
		ReadBufferSize:  1024,
		WriteBufferSize: 1024,
		CheckOrigin: func(r *http.Request) bool {
			return true // Allow all origins for now
		},
	}

	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("WS: Upgrade error: %v", err)
		return
	}

	client := &Client{hub: s.hub, conn: conn, send: make(chan []byte, 256)}
	s.hub.register <- client

	// Start pumps
	go client.writePump()
	go client.readPump()
}

type BudgetResponse struct {
	ID                int     `json:"id"`
	TargetType        string  `json:"target_type"`
	TargetID          string  `json:"target_id"`
	DailySessionLimit int     `json:"daily_session_limit"`
	MonthlyCostLimit  float64 `json:"monthly_cost_limit"`
	AlertThreshold    float64 `json:"alert_threshold"`
}

func (s *AdminServer) handleBudgets(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		rows, err := s.db.QueryContext(r.Context(), "SELECT id, target_type, COALESCE(target_id, ''), daily_session_limit, monthly_cost_limit, alert_threshold FROM budgets")
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		defer rows.Close()

		budgets := []BudgetResponse{}
		for rows.Next() {
			var b BudgetResponse
			if err := rows.Scan(&b.ID, &b.TargetType, &b.TargetID, &b.DailySessionLimit, &b.MonthlyCostLimit, &b.AlertThreshold); err == nil {
				budgets = append(budgets, b)
			}
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(budgets)

	case http.MethodPost:
		var b BudgetResponse
		if err := json.NewDecoder(r.Body).Decode(&b); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		_, err := s.db.ExecContext(r.Context(), 
			"INSERT INTO budgets (target_type, target_id, daily_session_limit, monthly_cost_limit, alert_threshold) VALUES (?, ?, ?, ?, ?)",
			b.TargetType, b.TargetID, b.DailySessionLimit, b.MonthlyCostLimit, b.AlertThreshold)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		w.WriteHeader(http.StatusCreated)

	case http.MethodPut:
		var b BudgetResponse
		if err := json.NewDecoder(r.Body).Decode(&b); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		_, err := s.db.ExecContext(r.Context(), 
			"UPDATE budgets SET daily_session_limit = ?, monthly_cost_limit = ?, alert_threshold = ? WHERE id = ?",
			b.DailySessionLimit, b.MonthlyCostLimit, b.AlertThreshold, b.ID)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		w.WriteHeader(http.StatusNoContent)

	case http.MethodDelete:
		id := r.URL.Query().Get("id")
		if id == "" {
			http.Error(w, "missing id", http.StatusBadRequest)
			return
		}
		_, err := s.db.ExecContext(r.Context(), "DELETE FROM budgets WHERE id = ?", id)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		w.WriteHeader(http.StatusNoContent)

	default:
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
	}
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
		remoteKey, remoteKeySource := s.effectiveKey(r.Context(), "llm_remote_api_key", "LLM_REMOTE_API_KEY")
		maskedRemote := maskSecret(remoteKey)
		if maskedRemote != "" {
			maskedRemote = "[" + remoteKeySource + "] " + maskedRemote
		}
		// dto_prompt_budget_effective shows the actual value the DTO will use:
		// either the explicit override stored in dto_prompt_budget_tokens, or the
		// value auto-detected from Ollama /api/show for the current local model.
		dtoBudgetOverride := s.getSetting(r.Context(), "dto_prompt_budget_tokens", "")
		dtoBudgetEffective := dtoBudgetOverride
		if dtoBudgetEffective == "" && s.analyzer != nil {
			dtoBudgetEffective = fmt.Sprintf("%d", s.analyzer.GetModelContextWindow())
		}
		json.NewEncoder(w).Encode(map[string]string{
			"local_model":                    s.getSetting(r.Context(), "llm_local_model", ""),
			"available_models":               os.Getenv("OLLAMA_AVAILABLE_MODELS"),
			"remote_model":                   s.getSetting(r.Context(), "llm_remote_model", ""),
			"remote_api_key":                 maskedRemote,
			"remote_endpoint_url":            s.getSetting(r.Context(), "llm_remote_endpoint", os.Getenv("LLM_REMOTE_ENDPOINT")),
			"jules_api_key":                  masked,
			"jules_base_url":                 s.getSetting(r.Context(), "jules_base_url", "https://jules.googleapis.com/v1alpha"),
			"local_context_window":           s.getSetting(r.Context(), "llm_local_context_window", "32768"),
			"local_temperature":              s.getSetting(r.Context(), "llm_local_temperature", "0.7"),
			"local_timeout":                  s.getSetting(r.Context(), "llm_local_timeout", "300"),
			"local_retries":                  s.getSetting(r.Context(), "llm_local_retries", "3"),
			"system_prompt":                  s.getSetting(r.Context(), "llm_system_prompt", "You are a professional coding assistant and project orchestrator."),
			"dto_prompt_budget_tokens":       dtoBudgetOverride,
			"dto_prompt_budget_effective":    dtoBudgetEffective,
		})
	case http.MethodPost:
		var data struct {
			LocalModel              string  `json:"local_model"`
			RemoteModel             string  `json:"remote_model"`
			RemoteAPIKey            string  `json:"remote_api_key"`
			RemoteEndpointURL       string  `json:"remote_endpoint_url"`
			JulesAPIKey             string  `json:"jules_api_key"`
			JulesBaseURL            string  `json:"jules_base_url"`
			LocalContextWindow      string  `json:"local_context_window"`
			LocalTemperature        string  `json:"local_temperature"`
			LocalTimeout            string  `json:"local_timeout"`
			LocalRetries            string  `json:"local_retries"`
			SystemPrompt            string  `json:"system_prompt"`
			// Pointer: nil = field absent (no change); "" = clear override; "N" = set override.
			DtoPromptBudgetTokens   *string `json:"dto_prompt_budget_tokens"`
		}
		json.NewDecoder(r.Body).Decode(&data)
		if data.LocalModel != "" {
			s.saveSetting(r.Context(), "llm_local_model", data.LocalModel)
			// Invalidate cached context-window so the next DTO run re-probes Ollama.
			if s.analyzer != nil {
				s.analyzer.InvalidateModelContextCache()
			}
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
		if data.RemoteAPIKey != "" {
			s.saveSetting(r.Context(), "llm_remote_api_key", data.RemoteAPIKey)
		}
		if data.RemoteEndpointURL != "" {
			s.saveSetting(r.Context(), "llm_remote_endpoint", data.RemoteEndpointURL)
		}
		if data.LocalTimeout != "" {
			s.saveSetting(r.Context(), "llm_local_timeout", data.LocalTimeout)
		}
		if data.LocalRetries != "" {
			s.saveSetting(r.Context(), "llm_local_retries", data.LocalRetries)
		}
		// nil = field absent (no change); "" = clear override; "N" = set override.
		if data.DtoPromptBudgetTokens != nil {
			s.saveSetting(r.Context(), "dto_prompt_budget_tokens", *data.DtoPromptBudgetTokens)
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
			"trigger_statuses":     statuses,
			"routing_simple":       s.getSetting(r.Context(), "routing_simple", "local"),
			"routing_complex":      s.getSetting(r.Context(), "routing_complex", "remote"),
			"routing_dto":          s.getSetting(r.Context(), "routing_dto", "local"),
			"complex_context_window": s.getSetting(r.Context(), "llm_complex_context_window", ""),
		})
	case http.MethodPost:
		var data struct {
			TriggerStatuses      []string `json:"trigger_statuses"`
			RoutingSimple        string   `json:"routing_simple"`
			RoutingComplex       string   `json:"routing_complex"`
			RoutingDTO           string   `json:"routing_dto"`
			ComplexContextWindow string   `json:"complex_context_window"`
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
		if data.RoutingDTO != "" {
			s.saveSetting(r.Context(), "routing_dto", data.RoutingDTO)
		}
		if data.ComplexContextWindow != "" {
			s.saveSetting(r.Context(), "llm_complex_context_window", data.ComplexContextWindow)
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

		patHint := ""
		if len(pat) >= 8 {
			patHint = pat[:4] + strings.Repeat("•", 8) + pat[len(pat)-4:]
		} else if pat != "" {
			patHint = strings.Repeat("•", len(pat))
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{
			"git_url":          s.db.GetSetting("prompt_library_git_url", ""),
			"git_branch":       s.db.GetSetting("prompt_library_git_branch", "main"),
			"cache_dir":        s.db.GetSetting("prompt_library_cache_dir", "/var/lib/orchestrator/prompt-lib"),
			"refresh_interval": s.db.GetSetting("prompt_library_refresh_interval", "1h"),
			"patterns_path":    s.db.GetSetting("prompt_library_patterns_path", "prompt/patterns"),
			"agents_path":      s.db.GetSetting("prompt_library_agents_path", ".agent/agents"),
			"workflows_path":   s.db.GetSetting("prompt_library_workflows_path", ".agent/workflows"),
			"pat_set":    func() string { if pat != "" { return "true" }; return "false" }(),
			"pat_hint":   patHint,
			"pat_source": patSource,
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
	results := []NextRun{}

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
	var sources []string
	if req.Repo != "" && s.analyzer != nil {
		res := s.analyzer.SearchContextFull(r.Context(), req.Repo, userMsg, 3, "")
		ragContext := res.Content
		sources = res.Sources

		if ragContext != "" {
			// Check total context size to respect Context Window settings
			windowStr := s.db.GetSetting("llm_local_context_window", "4096")
			var window int
			fmt.Sscanf(windowStr, "%d", &window)
			if window <= 0 { window = 4096 }
			maxChars := window * 3 // Conservative estimate

			currentChars := 0
			for _, m := range req.Messages {
				currentChars += len(m["content"])
			}

			ragMsgContent := fmt.Sprintf("Use the following context from repository '%s' to answer the question:\n%s", req.Repo, ragContext)
			
			// If adding RAG exceeds maxChars, truncate RAG context
			if currentChars + len(ragMsgContent) > maxChars {
				allowedRAG := maxChars - currentChars - 100 // leave some buffer
				if allowedRAG > 100 {
					log.Printf("Chat: RAG context too large (%d), truncating to %d", len(ragMsgContent), allowedRAG)
					ragMsgContent = ragMsgContent[:allowedRAG] + "... [truncated to fit context window]"
				} else {
					log.Printf("Chat: Context window full (%d), skipping RAG", currentChars)
					ragMsgContent = "" // Skip RAG if no space left
				}
			}

			if ragMsgContent != "" {
				ragMsg := map[string]string{
					"role":    "system",
					"content": ragMsgContent,
				}
				// Prepend RAG context to help the model
				req.Messages = append([]map[string]string{ragMsg}, req.Messages...)
			}
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
	
	// Send sources if available
	if len(sources) > 0 {
		fmt.Fprintf(w, "data: [SOURCES]%s\n\n", strings.Join(sources, ","))
		flusher.Flush()
	}

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

func (s *AdminServer) handleChatHistory(w http.ResponseWriter, r *http.Request) {
	repo := r.URL.Query().Get("repo")
	switch r.Method {
	case http.MethodGet:
		history, err := s.db.GetChatHistory(r.Context(), repo, 50)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(history)
	case http.MethodDelete:
		if err := s.db.ClearChatHistory(r.Context(), repo); err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		w.WriteHeader(http.StatusNoContent)
	default:
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
	}
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

	// Check if this is a service task
	var pattern string
	err := s.db.QueryRowContext(r.Context(), "SELECT pattern FROM tasks WHERE id = ?", taskID).Scan(&pattern)
	if err == nil {
		servicePatterns := []string{"discovery", "story_writer", "sprint_planner", "full_cycle", "sprint_closer"}
		for _, p := range servicePatterns {
			if p == pattern {
				http.Error(w, "cannot pause service tasks", http.StatusForbidden)
				return
			}
		}
	}

	_, err = s.db.ExecContext(r.Context(), "UPDATE tasks SET status = 'PAUSED', pending_decision = '' WHERE id = ?", taskID)
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
	taskRows, err := s.db.Main().QueryContext(r.Context(), "SELECT id, name, agent, mission, pattern FROM tasks")
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	defer taskRows.Close()
	taskMap := make(map[string]struct {
		Name    string
		Agent   string
		Mission string
		Pattern string
	})
	for taskRows.Next() {
		var id, name, agent, mission, pattern string
		if err := taskRows.Scan(&id, &name, &agent, &mission, &pattern); err == nil {
			taskMap[id] = struct {
				Name    string
				Agent   string
				Mission string
				Pattern string
			}{name, agent, mission, pattern}
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

	logs := []map[string]any{}
	for rows.Next() {
		var id int
		var taskID, executedAt, status string
		var sessionID, errorMsg sql.NullString
		var duration int
		if err := rows.Scan(&id, &taskID, &sessionID, &executedAt, &status, &errorMsg, &duration); err != nil {
			log.Printf("Scan error: %v", err)
			continue
		}

		tInfo := taskMap[taskID]
		logs = append(logs, map[string]any{
			"id":          id,
			"task_id":      taskID,
			"session_id":   sessionID.String,
			"executed_at":  executedAt,
			"status":       status,
			"error":        errorMsg.String,
			"duration_ms":  duration,
			"repo_name":    tInfo.Name,
			"agent":        tInfo.Agent,
			"mission":      tInfo.Mission,
			"pattern":      tInfo.Pattern,
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

	if s.budgetMgr != nil {
		if summary, err := s.budgetMgr.GetSummary(r.Context()); err == nil {
			stats["budget"] = summary
		}
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(stats)
}

func (s *AdminServer) handleSystemSettings(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		limit, _ := s.db.GetDailyLimit(r.Context())
		retentionStr := s.db.GetSetting("retention_days", "7")
		var retention int
		fmt.Sscanf(retentionStr, "%d", &retention)

		dtoBatchSizeStr := s.db.GetSetting("dto_batch_size", "500")
		var dtoBatchSize int
		fmt.Sscanf(dtoBatchSizeStr, "%d", &dtoBatchSize)

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]any{
			"daily_task_limit": limit,
			"retention_days":   retention,
			"dto_batch_size":   dtoBatchSize,
		})
	case http.MethodPost:
		var data struct {
			DailyTaskLimit int `json:"daily_task_limit"`
			RetentionDays  int `json:"retention_days"`
			DtoBatchSize   int `json:"dto_batch_size"`
		}
		if err := json.NewDecoder(r.Body).Decode(&data); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		s.db.SetSetting("daily_task_limit", fmt.Sprintf("%d", data.DailyTaskLimit))
		if data.RetentionDays > 0 {
			s.db.SetSetting("retention_days", fmt.Sprintf("%d", data.RetentionDays))
		}
		if data.DtoBatchSize > 0 {
			s.db.SetSetting("dto_batch_size", fmt.Sprintf("%d", data.DtoBatchSize))
		}
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

	log.Printf("DTO: Triggering manual analysis for repo: %s", repoName)
	s.analyzer.TriggerManualAnalysis(r.Context(), repoName)

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusAccepted)
	json.NewEncoder(w).Encode(map[string]string{
		"status":  "analysis_started",
		"message": "Repository analysis is running in the background",
	})
}

func (s *AdminServer) handleDTOStatus(w http.ResponseWriter, r *http.Request) {
	repoName := r.URL.Query().Get("repo")
	if repoName == "" {
		http.Error(w, "missing repo parameter", http.StatusBadRequest)
		return
	}

	lastAnalysis := s.db.GetSetting("dto_last_analysis_"+repoName, "")
	currentStatus := s.analyzer.GetStatus(repoName)

	resp := map[string]any{
		"last_analysis":   lastAnalysis,
		"is_running":      currentStatus.IsRunning,
		"type":            currentStatus.Type,
		"phase":           currentStatus.Phase,
		"current_file":    currentStatus.CurrentFile,
		"files_indexed":   currentStatus.FilesIndexed,
		"already_indexed": currentStatus.AlreadyIndexed,
		"total_files":     currentStatus.TotalFiles,
	}

	// Add RAG status if available
	if s.analyzer != nil && s.analyzer.GetRagManager() != nil {
		if store := s.analyzer.GetRagManager().GetStore(repoName); store != nil {
			ragStats := store.GetStats()
			resp["rag_status"] = ragStats.Status
			resp["rag_mode"] = ragStats.StorageMode
			resp["rag_chunks"] = ragStats.ChunkCount
		}
	}

	if p := currentStatus.Proposals; p != nil {
		resp["current_stage"] = p.CurrentStage
		resp["progress"] = int(p.Progress)
		resp["proposals"] = p.Proposals
		resp["warnings"] = p.Warnings
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(resp)
}

func (s *AdminServer) handleDTOChat(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var data struct {
		Repo     string `json:"repo"`
		Message  string `json:"message"`
		Provider string `json:"provider"` // "internal" or "external"
	}
	if err := json.NewDecoder(r.Body).Decode(&data); err != nil {
		http.Error(w, "invalid payload", http.StatusBadRequest)
		return
	}

	if data.Repo == "" || data.Message == "" {
		http.Error(w, "missing repo or message", http.StatusBadRequest)
		return
	}

	mgr := s.analyzer.GetSessionManager()
	if mgr == nil {
		http.Error(w, "session manager not initialized", http.StatusInternalServerError)
		return
	}

	session, err := mgr.GetSession(r.Context(), data.Repo)
	if err != nil {
		http.Error(w, "failed to get session", http.StatusInternalServerError)
		return
	}

	// Update provider if specified
	if data.Provider != "" {
		session.LLMProvider = data.Provider
	}

	// 1. Save user message
	userMsg := dto.DialogueMessage{Role: "user", Content: data.Message}
	session.Context = append(session.Context, userMsg)
	session.Status = "DIALOGUE"
	mgr.SaveSession(r.Context(), session)

	// 2. Prepare prompt for LLM
	// We use the internal router to generate a response
	systemPrompt := "You are a Project Discovery Agent. Help the user define their project requirements.\n" +
		"Use the provided context about the repository to ask relevant questions."
	
	// Convert session context to LLM messages
	llmMessages := []map[string]string{
		{"role": "system", "content": systemPrompt},
	}
	for _, m := range session.Context {
		llmMessages = append(llmMessages, map[string]string{"role": m.Role, "content": m.Content})
	}

	// Choose provider
	llmType := llm.DTO
	if session.LLMProvider == "external" {
		llmType = llm.Complex // Use Complex tier for higher quality external LLM
	}

	response, err := s.analyzer.GenerateDialogueResponse(r.Context(), llmType, llmMessages)
	if err != nil {
		http.Error(w, fmt.Sprintf("LLM error: %v", err), http.StatusInternalServerError)
		return
	}

	// 3. Save assistant message
	asstMsg := dto.DialogueMessage{Role: "assistant", Content: response}
	session.Context = append(session.Context, asstMsg)
	mgr.SaveSession(r.Context(), session)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]any{
		"response": response,
		"session":  session,
	})
}

func (s *AdminServer) handleDTOSession(w http.ResponseWriter, r *http.Request) {
	repo := r.URL.Query().Get("repo")
	if repo == "" {
		http.Error(w, "missing repo parameter", http.StatusBadRequest)
		return
	}

	mgr := s.analyzer.GetSessionManager()
	if mgr == nil {
		http.Error(w, "session manager not initialized", http.StatusInternalServerError)
		return
	}

	session, err := mgr.GetSession(r.Context(), repo)
	if err != nil {
		http.Error(w, "failed to get session", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(session)
}

func (s *AdminServer) handleDTOClearSession(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	repo := r.URL.Query().Get("repo")
	if repo == "" {
		http.Error(w, "missing repo parameter", http.StatusBadRequest)
		return
	}

	mgr := s.analyzer.GetSessionManager()
	if mgr == nil {
		http.Error(w, "session manager not initialized", http.StatusInternalServerError)
		return
	}

	if err := mgr.ClearSession(r.Context(), repo); err != nil {
		http.Error(w, "failed to clear session", http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

func (s *AdminServer) handleDTOFinalize(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var data struct {
		Repo  string `json:"repo"`
		Stage string `json:"stage"`
	}
	if err := json.NewDecoder(r.Body).Decode(&data); err != nil {
		http.Error(w, "invalid payload", http.StatusBadRequest)
		return
	}

	if data.Repo == "" || data.Stage == "" {
		http.Error(w, "missing repo or stage", http.StatusBadRequest)
		return
	}

	if err := s.analyzer.FinalizeStage(r.Context(), data.Repo, data.Stage); err != nil {
		http.Error(w, fmt.Sprintf("Finalization failed: %v", err), http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "success"})
}

func (s *AdminServer) handleRAGStats(w http.ResponseWriter, r *http.Request) {
	if s.analyzer == nil || s.analyzer.GetRagManager() == nil {
		http.Error(w, "RAG system not initialized", http.StatusServiceUnavailable)
		return
	}
	stats := s.analyzer.GetRagManager().GetAllStats()
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(stats)
}

func (s *AdminServer) handleRAGAction(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var data struct {
		Action string `json:"action"`
		RepoID string `json:"repo_id"`
	}
	if err := json.NewDecoder(r.Body).Decode(&data); err != nil {
		http.Error(w, "invalid payload", http.StatusBadRequest)
		return
	}

	if s.analyzer == nil || s.analyzer.GetRagManager() == nil {
		http.Error(w, "RAG system not initialized", http.StatusServiceUnavailable)
		return
	}
	mgr := s.analyzer.GetRagManager()

	switch data.Action {
	case "scrub_all":
		removed, err := mgr.ScrubAll(r.Context())
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		json.NewEncoder(w).Encode(map[string]any{"removed": removed})
	case "recover_repo":
		if data.RepoID == "" {
			http.Error(w, "missing repo_id", http.StatusBadRequest)
			return
		}
		// Use analyzer to recover, as it can auto-initialize the store if needed
		if err := s.analyzer.RecoverRepo(r.Context(), data.RepoID); err != nil {
			log.Printf("API: RAG recovery failed for %s: %v", data.RepoID, err)
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		json.NewEncoder(w).Encode(map[string]any{"status": "ok", "message": "Recovery successful"})
	case "scrub":
		if data.RepoID == "" {
			http.Error(w, "repo_id required", http.StatusBadRequest)
			return
		}
		store := mgr.GetStore(data.RepoID)
		if store == nil {
			http.Error(w, "repo not found in RAG index", http.StatusNotFound)
			return
		}
		go func() {
			removed, err := store.Scrub(context.Background(), nil)
			if err != nil {
				log.Printf("API: RAG scrub failed for %s: %v", data.RepoID, err)
			} else {
				log.Printf("API: RAG scrub completed for %s: removed %d orphaned chunks", data.RepoID, removed)
			}
		}()
		w.WriteHeader(http.StatusAccepted)
	case "reset":
		if data.RepoID == "" {
			http.Error(w, "repo_id required", http.StatusBadRequest)
			return
		}
		store := mgr.GetStore(data.RepoID)
		if store == nil {
			http.Error(w, "repo not found in RAG index", http.StatusNotFound)
			return
		}
		store.Reset(context.Background())
		log.Printf("API: RAG index reset for %s", data.RepoID)
		w.WriteHeader(http.StatusNoContent)
	default:
		http.Error(w, "unknown action", http.StatusBadRequest)
	}
}
func (s *AdminServer) BroadcastStatus(ctx context.Context) {
	if s.hub == nil {
		return
	}

	// 1. Health Status
	if s.healthMonitor != nil {
		s.hub.Broadcast(TypeStats, s.healthMonitor.GetStatus())
	}

	// 2. System Stats (CPU/Memory)
	if s.statsAggregator != nil {
		s.hub.Broadcast(TypeSysStats, s.statsAggregator.GetLatest())
	}

	// 3. Drift Status
	if s.driftDetector != nil {
		results := s.driftDetector.GetLastResults()
		hasDrift := false
		for _, r := range results {
			if r.HasDrift {
				hasDrift = true
				break
			}
		}
		if hasDrift {
			s.hub.Broadcast(TypeStats, map[string]any{
				"component": "drift",
				"status":    "diverged",
				"details":   results,
			})
		} else if len(results) > 0 {
			s.hub.Broadcast(TypeStats, map[string]any{
				"component": "drift",
				"status":    "synced",
			})
		}
	}

	// 3. System Usage (Quota)
	usage, _ := s.db.GetDailyUsage(ctx)
	limit, _ := s.db.GetDailyLimit(ctx)
	upcoming, _ := s.db.GetUpcomingTaskCountToday(ctx)
	s.hub.Broadcast(TypeSysUsage, map[string]any{
		"usage":    usage,
		"limit":    limit,
		"forecast": usage + upcoming,
	})

	// 4. Next Runs
	parser := cron.NewParser(cron.Minute | cron.Hour | cron.Dom | cron.Month | cron.Dow)
	now := time.Now()
	rows, err := s.db.Main().QueryContext(ctx, "SELECT id, name, schedule FROM tasks WHERE status != 'PAUSED'")
	if err == nil {
		defer rows.Close()
		var runs []map[string]any
		for rows.Next() {
			var id, name, schedule string
			if err := rows.Scan(&id, &name, &schedule); err == nil {
				if sched, err := parser.Parse(schedule); err == nil {
					next := sched.Next(now)
					runs = append(runs, map[string]any{
						"task_id":       id,
						"name":          name,
						"schedule":      schedule,
						"next_run":      next.Format(time.RFC3339),
						"seconds_until": next.Sub(now).Seconds(),
					})
				}
			}
		}
		// Sort by seconds until
		sort.Slice(runs, func(i, j int) bool {
			return runs[i]["seconds_until"].(float64) < runs[j]["seconds_until"].(float64)
		})
		s.hub.Broadcast(TypeNextRuns, runs)
	}
}

func (s *AdminServer) handleJulesWebhook(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	secret := os.Getenv("JULES_WEBHOOK_SECRET")
	if secret != "" {
		if r.Header.Get("X-Jules-Signature") != secret {
			http.Error(w, "invalid signature", http.StatusUnauthorized)
			return
		}
	}

	var payload monitor.WebhookEvent
	if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	if s.webhookBus != nil {
		select {
		case s.webhookBus <- payload:
			// Pushed to event bus successfully
		default:
			log.Printf("Webhook event bus is full, dropping event for session %s", payload.SessionID)
		}
	}

	// Trigger UI refresh immediately
	if s.hub != nil {
		s.hub.Broadcast(TypeActivity, nil)
	}

	w.WriteHeader(http.StatusAccepted)
}

func (s *AdminServer) handleRAGSearch(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req struct {
		Query  string `json:"query"`
		RepoID string `json:"repo_id"`
		TopK   int    `json:"top_k"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "invalid payload", http.StatusBadRequest)
		return
	}

	if req.Query == "" {
		http.Error(w, "query is required", http.StatusBadRequest)
		return
	}
	if req.TopK <= 0 {
		req.TopK = 5
	}

	if s.analyzer == nil || s.analyzer.GetRagManager() == nil {
		http.Error(w, "RAG system not initialized", http.StatusServiceUnavailable)
		return
	}
	mgr := s.analyzer.GetRagManager()

	results := []rag.Document{}
	if req.RepoID != "" {
		store := mgr.GetStore(req.RepoID)
		if store == nil {
			http.Error(w, "repo not found in RAG index", http.StatusNotFound)
			return
		}
		results = store.Search(r.Context(), req.Query, req.TopK)
	} else {
		// Search across all repos if no repo_id specified
		allStats := mgr.GetAllStats()
		for _, stat := range allStats {
			store := mgr.GetStore(stat.RepoID)
			if store != nil {
				res := store.Search(r.Context(), req.Query, req.TopK)
				results = append(results, res...)
			}
		}
		// Sort and limit if searching multiple
		sort.Slice(results, func(i, j int) bool {
			// Note: chromem-go results don't expose similarity score in the Document struct directly
			// in this implementation, so we just keep them appended. 
			// In a more advanced version we'd rank them.
			return false 
		})
		if len(results) > req.TopK {
			results = results[:req.TopK]
		}
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(results)
}

func (s *AdminServer) handleDriftStatus(w http.ResponseWriter, r *http.Request) {
	if s.driftDetector == nil {
		http.Error(w, "drift detector not initialized", http.StatusServiceUnavailable)
		return
	}

	results, err := s.driftDetector.CheckDrift(r.Context())
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(results)
}
