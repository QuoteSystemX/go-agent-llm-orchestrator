package api

import (
	"context"
	"encoding/json"
	"net/http"
	"os"
	"runtime"
	"sort"
	"strings"
	"time"

	"go-agent-llm-orchestrator/internal/backup"
	"go-agent-llm-orchestrator/internal/budget"
	"go-agent-llm-orchestrator/internal/db"
	"go-agent-llm-orchestrator/internal/dto"
	"go-agent-llm-orchestrator/internal/llm"
	"go-agent-llm-orchestrator/internal/monitor"
	"go-agent-llm-orchestrator/internal/traffic"
	"go-agent-llm-orchestrator/web"
	"github.com/robfig/cron/v3"
)

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
	hub             *Hub
	budgetMgr       *budget.Manager
	driftDetector   *monitor.DriftDetector
	trafficManager  *traffic.TrafficManager
	backupMgr       *backup.Manager
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

func (s *AdminServer) SetLogBuffer(lb *LogBuffer) { s.logBuf = lb }
func (s *AdminServer) SetGitSyncer(gs GitSyncer) { s.gitSyncer = gs }
func (s *AdminServer) SetPromptChecker(pc PromptChecker) { s.promptChecker = pc }
func (s *AdminServer) SetHealthMonitor(hm *monitor.HealthMonitor) { s.healthMonitor = hm }
func (s *AdminServer) SetHub(h *Hub) { s.hub = h }
func (s *AdminServer) SetWebhookBus(bus chan<- monitor.WebhookEvent) { s.webhookBus = bus }
func (s *AdminServer) SetBudgetManager(bm *budget.Manager) { s.budgetMgr = bm }
func (s *AdminServer) SetDriftDetector(dd *monitor.DriftDetector) { s.driftDetector = dd }
func (s *AdminServer) SetTrafficManager(tm *traffic.TrafficManager) { s.trafficManager = tm }
func (s *AdminServer) SetBackupManager(bm *backup.Manager) { s.backupMgr = bm }

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
	
	mux.HandleFunc("/api/v1/tasks/next-runs", s.handleNextRuns)
	mux.HandleFunc("/api/v1/tasks", s.handleTasks)
	mux.HandleFunc("/api/v1/tasks/", s.handleTaskByID)
	mux.HandleFunc("/api/v1/tasks/approve", s.handleApproveTask)
	mux.HandleFunc("/api/v1/tasks/reject", s.handleRejectTask)
	mux.HandleFunc("/api/v1/tasks/pause-loop", s.handlePauseTaskLoop)
	mux.HandleFunc("/api/v1/tasks/force-success", s.handleForceTaskSuccess)

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
	mux.HandleFunc("/api/v1/system/export", s.handleExport)
	mux.HandleFunc("/api/v1/system/import", s.handleImport)

	mux.HandleFunc("/api/v1/dto/templates", s.handleTemplates)
	mux.HandleFunc("/api/v1/dto/templates/", s.handleTemplateByID)
	mux.HandleFunc("/api/v1/dto/analyze", s.handleAnalyze)
	mux.HandleFunc("/api/v1/dto/status", s.handleDTOStatus)
	mux.HandleFunc("/api/v1/dto/chat", s.handleDTOChat)
	mux.HandleFunc("/api/v1/dto/session", s.handleDTOSession)
	mux.HandleFunc("/api/v1/dto/session/clear", s.handleDTOClearSession)
	mux.HandleFunc("/api/v1/dto/finalize", s.handleDTOFinalize)
	
	mux.HandleFunc("/api/v1/rag/stats", s.handleRAGStats)
	mux.HandleFunc("/api/v1/rag/action", s.handleRAGAction)
	mux.HandleFunc("/api/v1/rag/search", s.handleRAGSearch)
	mux.HandleFunc("/api/v1/budgets", s.handleBudgets)

	mux.HandleFunc("/api/v1/webhooks/telegram", s.handleTelegramWebhook)
	mux.HandleFunc("/api/v1/logs", s.handleLogs)
	mux.HandleFunc("/api/v1/ws", s.handleWS)
	mux.HandleFunc("/healthz", s.handleHealth)
	mux.HandleFunc("/readyz", s.handleHealth)
	
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/" {
			http.NotFound(w, r)
			return
		}
		w.Header().Set("Content-Type", "text/html")
		w.Write([]byte(`
			<!DOCTYPE html>
			<html>
			<head><title>Agentic Orchestrator</title></head>
			<body style="font-family: sans-serif; text-align: center; padding-top: 50px; background: #0f172a; color: white;">
				<h1>Welcome to Agentic Orchestrator 🤖</h1>
				<p>Your autonomous agents are under control.</p>
				<a href="/dashboard" style="display: inline-block; padding: 12px 24px; background: #3b82f6; color: white; text-decoration: none; border-radius: 8px; font-weight: bold; transition: background 0.3s;">Go to Dashboard</a>
				<br><br>
				<small style="color: #64748b;">API Version: v1 (Autonomous Mode)</small>
			</body>
			</html>
		`))
	})
	
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
	rows, err := s.db.QueryContext(r.Context(),
		`SELECT id, name, COALESCE(agent,''), mission, pattern, schedule, status, importance, category, last_run_at, created_at, failure_count,
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
		if err := rows.Scan(&t.ID, &t.Name, &t.Agent, &t.Mission, &t.Pattern, &t.Schedule, &t.Status, &t.Importance, &t.Category, &t.LastRunAt, &t.CreatedAt, &t.FailureCount, &t.LastError, &t.MaxRetries, &t.CurrentRetry); err != nil {
			continue
		}
		tasks = append(tasks, t)
	}
	rows.Close()

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

	for i := range tasks {
		if s.promptChecker != nil {
			tasks[i].PromptReady = s.promptChecker.HasPrompt(tasks[i].Agent, tasks[i].Pattern, tasks[i].Mission)
		} else {
			tasks[i].PromptReady = true
		}
		tasks[i].LastError = lastErrors[tasks[i].ID]

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

	if t.Agent == "" {
		t.Agent = s.getSetting(r.Context(), "default_agent", "analyst")
	}
	if t.Pattern == "" {
		t.Pattern = s.getSetting(r.Context(), "default_pattern", "discovery")
	}

	_, err := s.db.ExecContext(r.Context(), 
		"INSERT INTO tasks (id, name, agent, mission, pattern, schedule, status, importance, category) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
		t.ID, t.Name, t.Agent, t.Mission, t.Pattern, t.Schedule, "PENDING", t.Importance, t.Category)
	
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	s.scheduler.NotifyTaskChange(t.ID)
	w.WriteHeader(http.StatusCreated)
}

func (s *AdminServer) handleTaskByID(w http.ResponseWriter, r *http.Request) {
	const prefix = "/api/v1/tasks/"
	rest := strings.TrimPrefix(r.URL.Path, prefix)
	if rest == "" {
		http.Error(w, "invalid path", http.StatusBadRequest)
		return
	}

	if strings.HasSuffix(rest, "/logs") {
		taskID := strings.TrimSuffix(rest, "/logs")
		s.listTaskLogs(w, r, taskID)
		return
	}

	for _, action := range []string{"run", "pause", "resume"} {
		if strings.HasSuffix(rest, "/"+action) {
			taskID := strings.TrimSuffix(rest, "/"+action)
			s.handleTaskAction(w, r, taskID, action)
			return
		}
	}

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

func (s *AdminServer) handleRunTask(w http.ResponseWriter, r *http.Request) {
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
	s.scheduler.TriggerTask(req.TaskID)
	w.WriteHeader(http.StatusAccepted)
}

func (s *AdminServer) handleListAudit(w http.ResponseWriter, r *http.Request) {
	rows, err := s.db.QueryContext(r.Context(), "SELECT id, session_id, action, details, created_at FROM audit_logs ORDER BY created_at DESC LIMIT 100")
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	type AuditLog struct {
		ID        int       `json:"id"`
		SessionID string    `json:"session_id"`
		Action    string    `json:"action"`
		Details   string    `json:"details"`
		CreatedAt time.Time `json:"created_at"`
	}

	logs := []AuditLog{}
	for rows.Next() {
		var l AuditLog
		if err := rows.Scan(&l.ID, &l.SessionID, &l.Action, &l.Details, &l.CreatedAt); err != nil {
			continue
		}
		logs = append(logs, l)
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(logs)
}

func (s *AdminServer) handleListAuditLogs(w http.ResponseWriter, r *http.Request) {
	rows, err := s.db.History().QueryContext(r.Context(), "SELECT id, task_id, status, error, duration_ms, created_at FROM task_logs ORDER BY created_at DESC LIMIT 100")
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	type TaskLog struct {
		ID         int       `json:"id"`
		TaskID     string    `json:"task_id"`
		Status     string    `json:"status"`
		Error      string    `json:"error"`
		DurationMS int       `json:"duration_ms"`
		CreatedAt  time.Time `json:"created_at"`
	}

	logs := []TaskLog{}
	for rows.Next() {
		var l TaskLog
		if err := rows.Scan(&l.ID, &l.TaskID, &l.Status, &l.Error, &l.DurationMS, &l.CreatedAt); err != nil {
			continue
		}
		logs = append(logs, l)
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(logs)
}

func (s *AdminServer) handleGetTaskRunDetails(w http.ResponseWriter, r *http.Request) {
	id := r.URL.Query().Get("id")
	if id == "" {
		http.Error(w, "missing id", http.StatusBadRequest)
		return
	}

	var l struct {
		ID         int       `json:"id"`
		TaskID     string    `json:"task_id"`
		Status     string    `json:"status"`
		Error      string    `json:"error"`
		FullOutput string    `json:"full_output"`
		DurationMS int       `json:"duration_ms"`
		CreatedAt  time.Time `json:"created_at"`
	}

	err := s.db.History().QueryRowContext(r.Context(), "SELECT id, task_id, status, error, full_output, duration_ms, created_at FROM task_logs WHERE id = ?", id).
		Scan(&l.ID, &l.TaskID, &l.Status, &l.Error, &l.FullOutput, &l.DurationMS, &l.CreatedAt)
	if err != nil {
		http.Error(w, err.Error(), http.StatusNotFound)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(l)
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

	resp, err := s.analyzer.GenerateDialogueResponse(r.Context(), llm.Simple, req.Messages)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"response": resp})
}

func (s *AdminServer) handleChatStream(w http.ResponseWriter, r *http.Request) {
	http.Error(w, "streaming not implemented for autonomous mode", http.StatusNotImplemented)
}

func (s *AdminServer) handleChatHistory(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode([]any{})
}

func (s *AdminServer) handleHealth(w http.ResponseWriter, r *http.Request) {
	if s.healthMonitor == nil {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status":"ok"}`))
		return
	}
	status := s.healthMonitor.GetStatus()
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(status)
}

func (s *AdminServer) handleSystemSettings(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		rows, err := s.db.QueryContext(r.Context(), "SELECT key, value FROM settings")
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		defer rows.Close()

		settings := map[string]string{}
		for rows.Next() {
			var k, v string
			if err := rows.Scan(&k, &v); err == nil {
				settings[k] = v
			}
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(settings)

	case http.MethodPost:
		var req map[string]string
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		for k, v := range req {
			_, _ = s.db.ExecContext(r.Context(), "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", k, v)
		}
		w.WriteHeader(http.StatusNoContent)
	}
}

func (s *AdminServer) handleSystemUsage(w http.ResponseWriter, r *http.Request) {
	var m runtime.MemStats
	runtime.ReadMemStats(&m)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]any{
		"alloc_mb":       m.Alloc / 1024 / 1024,
		"total_alloc_mb": m.TotalAlloc / 1024 / 1024,
		"sys_mb":         m.Sys / 1024 / 1024,
		"num_gc":         m.NumGC,
		"goroutines":     runtime.NumGoroutine(),
		"uptime_sec":     time.Since(s.startTime).Seconds(),
	})
}

func (s *AdminServer) handleSystemStats(w http.ResponseWriter, r *http.Request) {
	if s.statsAggregator == nil {
		http.Error(w, "stats aggregator not initialized", http.StatusServiceUnavailable)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(s.statsAggregator.GetLatest())
}

func (s *AdminServer) handleDriftStatus(w http.ResponseWriter, r *http.Request) {
	if s.driftDetector == nil {
		http.Error(w, "drift detector not initialized", http.StatusServiceUnavailable)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(s.driftDetector.GetLastResults())
}

func (s *AdminServer) handleTrafficStatus(w http.ResponseWriter, r *http.Request) {
	if s.trafficManager == nil {
		http.Error(w, "traffic manager not initialized", http.StatusServiceUnavailable)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(s.trafficManager.GetQueue())
}

func (s *AdminServer) handleExport(w http.ResponseWriter, r *http.Request) {
	http.Error(w, "export not implemented", http.StatusNotImplemented)
}

func (s *AdminServer) handleImport(w http.ResponseWriter, r *http.Request) {
	http.Error(w, "import not implemented", http.StatusNotImplemented)
}

func (s *AdminServer) handleTemplates(w http.ResponseWriter, r *http.Request) {
	templates, err := s.dtoMgr.ListTemplates(r.Context())
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(templates)
}

func (s *AdminServer) handleTemplateByID(w http.ResponseWriter, r *http.Request) {
	parts := strings.Split(r.URL.Path, "/")
	if len(parts) < 5 {
		http.Error(w, "invalid path", http.StatusBadRequest)
		return
	}
	name := parts[4]
	tpl, err := s.dtoMgr.GetTemplate(r.Context(), name)
	if err != nil {
		http.Error(w, err.Error(), http.StatusNotFound)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(tpl)
}

func (s *AdminServer) handleAnalyze(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req struct {
		RepoURL string `json:"repo_url"`
		Force   bool   `json:"force"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	state, err := s.analyzer.AnalyzeRepo(r.Context(), req.RepoURL, req.Force)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(state)
}

func (s *AdminServer) handleDTOStatus(w http.ResponseWriter, r *http.Request) {
	repoURL := r.URL.Query().Get("repo")
	if repoURL == "" {
		http.Error(w, "missing repo", http.StatusBadRequest)
		return
	}
	state := s.analyzer.GetStatus(repoURL)
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(state)
}

func (s *AdminServer) handleDTOChat(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req struct {
		RepoURL  string              `json:"repo_url"`
		Messages []map[string]string `json:"messages"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	resp, err := s.analyzer.GenerateDialogueResponse(r.Context(), llm.Complex, req.Messages)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"response": resp})
}

func (s *AdminServer) handleDTOSession(w http.ResponseWriter, r *http.Request) {
	repoURL := r.URL.Query().Get("repo")
	if repoURL == "" {
		http.Error(w, "missing repo", http.StatusBadRequest)
		return
	}
	session, _, _ := s.analyzer.GetSessionManager().GetSession(r.Context(), repoURL)
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(session)
}

func (s *AdminServer) handleDTOClearSession(w http.ResponseWriter, r *http.Request) {
	repoURL := r.URL.Query().Get("repo")
	if repoURL == "" {
		http.Error(w, "missing repo", http.StatusBadRequest)
		return
	}
	s.analyzer.GetSessionManager().ClearSession(r.Context(), repoURL)
	w.WriteHeader(http.StatusNoContent)
}

func (s *AdminServer) handleDTOFinalize(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusNoContent)
}

func (s *AdminServer) handleRAGStats(w http.ResponseWriter, r *http.Request) {
	repoURL := r.URL.Query().Get("repo")
	if repoURL == "" {
		http.Error(w, "missing repo", http.StatusBadRequest)
		return
	}

	if s.analyzer == nil {
		http.Error(w, "analyzer not initialized", http.StatusServiceUnavailable)
		return
	}

	store := s.analyzer.GetRagStore(repoURL)
	if store == nil {
		http.Error(w, "store not found", http.StatusNotFound)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(store.GetStats())
}

func (s *AdminServer) handleRAGAction(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req struct {
		RepoURL string `json:"repo_url"`
		Action  string `json:"action"` // "index", "clear"
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	if s.analyzer == nil {
		http.Error(w, "analyzer not initialized", http.StatusServiceUnavailable)
		return
	}

	switch req.Action {
	case "index":
		go func() {
			_, _ = s.analyzer.AnalyzeRepo(context.Background(), req.RepoURL, true)
		}()
	case "clear":
		// Clear local store
	default:
		http.Error(w, "invalid action", http.StatusBadRequest)
		return
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
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	if s.analyzer == nil {
		http.Error(w, "analyzer not initialized", http.StatusServiceUnavailable)
		return
	}

	result := s.analyzer.SearchContextFiltered(r.Context(), req.RepoID, req.Query, req.TopK, "")
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"result": result})
}

func (s *AdminServer) handleBudgets(w http.ResponseWriter, r *http.Request) {
	if s.budgetMgr == nil {
		http.Error(w, "budget manager not initialized", http.StatusServiceUnavailable)
		return
	}

	switch r.Method {
	case http.MethodGet:
		budgets, err := s.budgetMgr.ListBudgets(r.Context())
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(budgets)

	case http.MethodPost:
		var b budget.Budget
		if err := json.NewDecoder(r.Body).Decode(&b); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		if err := s.budgetMgr.UpsertBudget(r.Context(), b); err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		w.WriteHeader(http.StatusNoContent)
	}
}

func (s *AdminServer) handleTelegramSettings(w http.ResponseWriter, r *http.Request) {
	s.handleSystemSettings(w, r)
}

func (s *AdminServer) handleLLMSettings(w http.ResponseWriter, r *http.Request) {
	s.handleSystemSettings(w, r)
}

func (s *AdminServer) handleSupervisorSettings(w http.ResponseWriter, r *http.Request) {
	s.handleSystemSettings(w, r)
}

func (s *AdminServer) handlePromptSettings(w http.ResponseWriter, r *http.Request) {
	s.handleSystemSettings(w, r)
}

func (s *AdminServer) handlePromptLibrarySettings(w http.ResponseWriter, r *http.Request) {
	s.handleSystemSettings(w, r)
}

func (s *AdminServer) handlePromptLibrarySync(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	if s.gitSyncer == nil {
		http.Error(w, "git syncer not initialized", http.StatusServiceUnavailable)
		return
	}
	if err := s.gitSyncer.Sync(r.Context()); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

func (s *AdminServer) handleTelegramWebhook(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusAccepted)
}

func (s *AdminServer) handleLogs(w http.ResponseWriter, r *http.Request) {
	if s.logBuf == nil {
		http.Error(w, "log buffer not initialized", http.StatusServiceUnavailable)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(s.logBuf.Entries())
}

func (s *AdminServer) handleWS(w http.ResponseWriter, r *http.Request) {
	if s.hub == nil {
		http.Error(w, "websocket hub not initialized", http.StatusServiceUnavailable)
		return
	}
	s.hub.ServeHTTP(w, r)
}

func (s *AdminServer) handleApproveTask(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusNoContent)
}

func (s *AdminServer) handleRejectTask(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusNoContent)
}

func (s *AdminServer) handleTaskAction(w http.ResponseWriter, r *http.Request, taskID, action string) {
	switch action {
	case "run":
		s.scheduler.TriggerTask(taskID)
	case "pause":
	case "resume":
	}
	w.WriteHeader(http.StatusAccepted)
}

func (s *AdminServer) listTaskLogs(w http.ResponseWriter, r *http.Request, taskID string) {
	rows, err := s.db.History().QueryContext(r.Context(), "SELECT id, status, error, duration_ms, created_at FROM task_logs WHERE task_id = ? ORDER BY created_at DESC LIMIT 50", taskID)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	type TaskLog struct {
		ID         int       `json:"id"`
		Status     string    `json:"status"`
		Error      string    `json:"error"`
		DurationMS int       `json:"duration_ms"`
		CreatedAt  time.Time `json:"created_at"`
	}

	logs := []TaskLog{}
	for rows.Next() {
		var l TaskLog
		if err := rows.Scan(&l.ID, &l.Status, &l.Error, &l.DurationMS, &l.CreatedAt); err != nil {
			continue
		}
		logs = append(logs, l)
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(logs)
}

func (s *AdminServer) handleNextRuns(w http.ResponseWriter, r *http.Request) {
	rows, err := s.db.QueryContext(r.Context(), "SELECT id, name, schedule FROM tasks WHERE status != 'PAUSED'")
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	parser := cron.NewParser(cron.Minute | cron.Hour | cron.Dom | cron.Month | cron.Dow)
	now := time.Now()
	runs := []map[string]any{}

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
	sort.Slice(runs, func(i, j int) bool {
		return runs[i]["seconds_until"].(float64) < runs[j]["seconds_until"].(float64)
	})

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(runs)
}

func (s *AdminServer) getSetting(ctx context.Context, key, defaultValue string) string {
	var val string
	err := s.db.QueryRowContext(ctx, "SELECT value FROM settings WHERE key = ?", key).Scan(&val)
	if err != nil {
		return defaultValue
	}
	return val
}

func (s *AdminServer) BroadcastStatus(ctx context.Context) {
	if s.hub == nil {
		return
	}
	status := map[string]any{
		"time": time.Now().Format(time.RFC3339),
	}
	if s.healthMonitor != nil {
		status["health"] = s.healthMonitor.GetStatus()
	}
	s.hub.Broadcast(TypeStats, status)
}

func (s *AdminServer) PrewarmDTOSession(ctx context.Context, repoURL string) {
	if s.analyzer == nil {
		return
	}
	_, _ = s.analyzer.AnalyzeRepo(ctx, repoURL, false)
}
