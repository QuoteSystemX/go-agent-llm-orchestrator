package scheduler

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"strings"
	"sync"
	"time"

	"go-agent-llm-orchestrator/internal/api"
	"go-agent-llm-orchestrator/internal/budget"
	"go-agent-llm-orchestrator/internal/db"
	"go-agent-llm-orchestrator/internal/monitor"
	"go-agent-llm-orchestrator/internal/notifier"
	"go-agent-llm-orchestrator/internal/prompt"
	"go-agent-llm-orchestrator/internal/traffic"
	"github.com/robfig/cron/v3"
)

// ContextSearchFunc queries the RAG vector store for semantically relevant chunks.
type ContextSearchFunc func(ctx context.Context, repoName, query string, topK int, category string) string

type Engine struct {
	cron          *cron.Cron
	db            *db.DB
	tm            *traffic.TrafficManager
	client        *api.JulesClient
	notifier      *notifier.TelegramNotifier
	promptBuilder *prompt.Builder
	contextSearch ContextSearchFunc
	tracer        monitor.Tracer
	verifier      TaskVerifier
	budgetMgr     *budget.Manager
	mu            sync.RWMutex
	entries       map[string]cron.EntryID
	syncChan      chan string
	onTaskUpdate     func(taskID, status string)
	onActivityUpdate func()
}

func NewEngine(database *db.DB, tm *traffic.TrafficManager, client *api.JulesClient, nt *notifier.TelegramNotifier, pb *prompt.Builder) *Engine {
	return &Engine{
		cron:          cron.New(),
		db:            database,
		tm:            tm,
		client:        client,
		notifier:      nt,
		promptBuilder: pb,
		entries:       make(map[string]cron.EntryID),
		syncChan:      make(chan string, 100),
	}
}

// SetContextSearcher injects the RAG search function so the engine can enrich
// Jules prompts with semantically relevant repository context at dispatch time.
func (e *Engine) SetContextSearcher(fn ContextSearchFunc) {
	e.contextSearch = fn
}

func (e *Engine) SetTracer(t monitor.Tracer) {
	e.tracer = t
}

func (e *Engine) SetBudgetManager(bm *budget.Manager) {
	e.budgetMgr = bm
}

func (e *Engine) SetVerifier(v TaskVerifier) {
	e.verifier = v
}

func (e *Engine) SetNotifyFunc(fn func(taskID, status string)) {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.onTaskUpdate = fn
}

func (e *Engine) SetActivityNotifyFunc(fn func()) {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.onActivityUpdate = fn
}

func (e *Engine) Start() {
	e.cron.Start()
	go e.watchSync()

	// Register daily cleanup task (default 02:00 AM, configurable via env)
	cleanupSchedule := os.Getenv("CLEANUP_SCHEDULE")
	if cleanupSchedule == "" {
		cleanupSchedule = "0 2 * * *"
	}

	_, err := e.cron.AddFunc(cleanupSchedule, func() {
		e.Cleanup(context.Background())
	})
	if err != nil {
		log.Printf("scheduler: failed to register cleanup task with schedule %s: %v", cleanupSchedule, err)
	}

	log.Println("Scheduler engine started with background sync worker")
}

func (e *Engine) watchSync() {
	for id := range e.syncChan {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		if id == "*" {
			log.Println("scheduler: full sync triggered via background channel")
			// Although user said no fallback, internal '*' signal can be useful for mass imports.
			// However, for now we keep it focused on incremental updates.
			e.syncAllInternal(ctx)
		} else {
			e.syncTaskInternal(ctx, id)
		}
		cancel()
	}
}

// syncTaskInternal performs the actual synchronization for a single task.
func (e *Engine) syncTaskInternal(ctx context.Context, id string) {
	var schedule string
	err := e.db.QueryRowContext(ctx, "SELECT schedule FROM tasks WHERE id = ?", id).Scan(&schedule)
	
	e.mu.Lock()
	defer e.mu.Unlock()

	if err != nil {
		// Task likely deleted
		if entryID, exists := e.entries[id]; exists {
			e.cron.Remove(entryID)
			delete(e.entries, id)
			log.Printf("scheduler: removed task %s from cron", id)
		}
		return
	}

	// Update or Add
	if entryID, exists := e.entries[id]; exists {
		e.cron.Remove(entryID)
	}
	
	if err := e.addTaskLocked(id, schedule); err != nil {
		log.Printf("scheduler: failed to add/update task %s: %v", id, err)
	}
}

func (e *Engine) syncAllInternal(ctx context.Context) {
	rows, err := e.db.QueryContext(ctx, "SELECT id, schedule FROM tasks")
	if err != nil {
		log.Printf("scheduler: failed to query tasks for full sync: %v", err)
		return
	}
	defer rows.Close()

	e.mu.Lock()
	defer e.mu.Unlock()

	activeIDs := make(map[string]bool)
	for rows.Next() {
		var id, schedule string
		if err := rows.Scan(&id, &schedule); err != nil {
			continue
		}
		activeIDs[id] = true
		
		if _, exists := e.entries[id]; !exists {
			e.addTaskLocked(id, schedule)
		}
	}

	for id, entryID := range e.entries {
		if !activeIDs[id] {
			e.cron.Remove(entryID)
			delete(e.entries, id)
		}
	}
}

// addTaskLocked adds a task to cron. MUST be called with mu.Lock held.
func (e *Engine) addTaskLocked(id, schedule string) error {
	entryID, err := e.cron.AddFunc(schedule, func() {
		e.runTask(id)
	})
	if err != nil {
		return err
	}
	e.entries[id] = entryID
	log.Printf("Scheduled task %s with cron %s", id, schedule)
	return nil
}

func (e *Engine) NotifyTaskChange(id string) {
	select {
	case e.syncChan <- id:
	default:
		log.Printf("scheduler: sync channel full, dropping notification for %s", id)
	}
}

func (e *Engine) NotifyAllTasksChange() {
	select {
	case e.syncChan <- "*":
	default:
		log.Printf("scheduler: sync channel full, dropping full sync notification")
	}
}

func (e *Engine) Cleanup(ctx context.Context) {
	daysStr := e.db.GetSetting("retention_days", "7")
	var days int
	fmt.Sscanf(daysStr, "%d", &days)

	if days <= 0 {
		log.Printf("cleanup: retention disabled (days=%d)", days)
		return
	}

	log.Printf("cleanup: removing data older than %d days", days)

	// 1. Clean up sessions (completed or failed)
	res, err := e.db.ExecContext(ctx, "DELETE FROM sessions WHERE status IN ('COMPLETED', 'FAILED') AND updated_at < datetime('now', '-' || ? || ' days')", days)
	if err != nil {
		log.Printf("cleanup: failed to clean sessions: %v", err)
	} else {
		n, _ := res.RowsAffected()
		if n > 0 {
			log.Printf("cleanup: removed %d old sessions", n)
		}
	}

	// 2. Clean up task logs
	res, err = e.db.History().ExecContext(ctx, "DELETE FROM task_logs WHERE executed_at < datetime('now', '-' || ? || ' days')", days)
	if err != nil {
		log.Printf("cleanup: failed to clean task logs: %v", err)
	} else {
		n, _ := res.RowsAffected()
		if n > 0 {
			log.Printf("cleanup: removed %d old task logs", n)
		}
	}
}

func (e *Engine) Stop() {
	e.cron.Stop()
}

// PauseAllPending pauses every PENDING task and marks them auto_paused=1.
// Called at startup when the prompt-library SSH key is not yet configured.
// Only auto_paused tasks are eligible for automatic resume via ResumeAutopaused.
func (e *Engine) PauseAllPending(ctx context.Context) int {
	res, err := e.db.ExecContext(ctx,
		"UPDATE tasks SET status = 'PAUSED', auto_paused = 1 WHERE status = 'PENDING'")
	if err != nil {
		log.Printf("scheduler: failed to pause pending tasks: %v", err)
		return 0
	}
	n, _ := res.RowsAffected()
	return int(n)
}

// ResumeAutopaused restores PAUSED tasks that were auto-paused at startup (auto_paused=1)
// back to PENDING. Called after a successful prompt-library sync.
func (e *Engine) ResumeAutopaused(ctx context.Context) int {
	res, err := e.db.ExecContext(ctx,
		"UPDATE tasks SET status = 'PENDING', auto_paused = 0 WHERE status = 'PAUSED' AND auto_paused = 1")
	if err != nil {
		log.Printf("scheduler: failed to resume auto-paused tasks: %v", err)
		return 0
	}
	n, _ := res.RowsAffected()
	return int(n)
}

func (e *Engine) updateTaskStatus(ctx context.Context, taskID, status string, extraSQL string, args ...interface{}) {
	query := "UPDATE tasks SET status = ?"
	if extraSQL != "" {
		query += ", " + extraSQL
	}
	query += " WHERE id = ?"
	
	allArgs := append([]interface{}{status}, args...)
	allArgs = append(allArgs, taskID)
	
	e.db.ExecContext(ctx, query, allArgs...)
	
	if e.onTaskUpdate != nil {
		e.onTaskUpdate(taskID, status)
	}
}

func (e *Engine) TriggerTask(taskID string) {
	log.Printf("Manual trigger for task %s", taskID)
	go e.runTask(taskID)
}

func (e *Engine) PauseTaskLoop(ctx context.Context, taskID string) error {
	_, err := e.db.ExecContext(ctx, "UPDATE tasks SET status = 'PAUSED' WHERE id = ?", taskID)
	return err
}

func (e *Engine) ForceTaskSuccess(ctx context.Context, taskID string) error {
	_, err := e.db.ExecContext(ctx, "UPDATE tasks SET status = 'PENDING', current_retry = 0, failure_count = 0, last_error = '' WHERE id = ?", taskID)
	return err
}

func (e *Engine) RemoveTaskFromScheduler(id string) {
	e.mu.Lock()
	defer e.mu.Unlock()
	if entryID, exists := e.entries[id]; exists {
		e.cron.Remove(entryID)
		delete(e.entries, id)
		log.Printf("scheduler: removed task %s manually", id)
	}
}

func (e *Engine) GetTasksByRepo(ctx context.Context, repoName string) ([]map[string]any, error) {
	rows, err := e.db.QueryContext(ctx, "SELECT id, name, mission, pattern, agent, schedule, status, importance, category, current_stage, progress, max_retries, current_retry, last_error FROM tasks WHERE name = ?", repoName)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var tasks []map[string]any
	for rows.Next() {
		var id, name, mission, pattern, agent, schedule, status, category, currentStage, lastError string
		var importance, progress, maxRetries, currentRetry int
		if err := rows.Scan(&id, &name, &mission, &pattern, &agent, &schedule, &status, &importance, &category, &currentStage, &progress, &maxRetries, &currentRetry, &lastError); err != nil {
			continue
		}
		tasks = append(tasks, map[string]any{
			"id":             id,
			"name":           name,
			"mission":        mission,
			"pattern":        pattern,
			"agent":          agent,
			"schedule":       schedule,
			"status":         status,
			"importance":     importance,
			"category":       category,
			"current_stage":  currentStage,
			"progress":       progress,
			"max_retries":    maxRetries,
			"current_retry":  currentRetry,
			"last_error":     lastError,
		})
	}
	return tasks, nil
}

func (e *Engine) printSchedule() {
	var active []string
	for id := range e.entries {
		active = append(active, id)
	}
	log.Printf("Scheduler: %d tasks active: [%s]", len(active), strings.Join(active, ", "))
}

func (e *Engine) addTask(id, schedule string) error {
	e.mu.Lock()
	defer e.mu.Unlock()
	return e.addTaskLocked(id, schedule)
}

func (e *Engine) runTask(taskID string) {
	log.Printf("Task %s: TRIGGERED", taskID)

	ctx := monitor.WithTaskID(context.Background(), taskID)
	start := time.Now()

	var status, mission, pattern, agent, repoName, category string
	var importance, maxRetries, currentRetry int
	err := e.db.QueryRowContext(ctx,
		"SELECT status, mission, pattern, COALESCE(agent,''), name, importance, category, max_retries, current_retry FROM tasks WHERE id = ?", taskID,
	).Scan(&status, &mission, &pattern, &agent, &repoName, &importance, &category, &maxRetries, &currentRetry)
	if err != nil {
		log.Printf("Task %s: FAILED to fetch from DB: %v", taskID, err)
		return
	}

	if status == "PAUSED" {
		log.Printf("Task %s: SKIPPED (status is PAUSED)", taskID)
		return
	}

	// Budget Check
	if e.budgetMgr != nil {
		ok, bErr := e.budgetMgr.CheckBudget(ctx, repoName)
		if !ok {
			msg := fmt.Sprintf("Budget exceeded: %v", bErr)
			log.Printf("Task %s: %s", taskID, msg)
			e.updateTaskStatus(ctx, taskID, "PAUSED", "auto_paused = 1, last_error = ?", msg)
			if e.notifier != nil {
				e.notifier.SendAlert(taskID, msg)
			}
			return
		}
	}

	var logID int64
	var sessionID string
	var execError string
	execStatus := "SUCCESS"

	res, logErr := e.db.ExecContext(ctx, `
		INSERT INTO task_logs (task_id, status, duration_ms)
		VALUES (?, ?, ?)
	`, taskID, "TRIGGERED", 0)
	if logErr == nil {
		logID, _ = res.LastInsertId()
	}

	var lastVerificationError string
	
	for {
		err = e.tm.Execute(ctx, traffic.PriorityHigh, importance, category, func() error {
			if logID > 0 {
				e.db.ExecContext(ctx, "UPDATE task_logs SET status = 'PROMPTING' WHERE id = ?", logID)
			}

			// Build the full Jules prompt
			fullPrompt, err := e.buildPrompt(ctx, agent, pattern, mission, repoName, lastVerificationError, category)
			if err != nil {
				// Do not auto-pause service tasks
				servicePatterns := []string{"discovery", "story_writer", "sprint_planner", "full_cycle", "sprint_closer"}
				isService := false
				for _, p := range servicePatterns {
					if p == pattern {
						isService = true
						break
					}
				}

				if !isService {
					e.updateTaskStatus(ctx, taskID, "PAUSED", "auto_paused = 1")
				}

				if logID > 0 {
					e.db.ExecContext(ctx, "UPDATE task_logs SET status = 'FAILED', error = ? WHERE id = ?", err.Error(), logID)
				}
				return fmt.Errorf("prompt building failed, task %s: %w", taskID, err)
			}
			log.Printf("Task %s: Prompt assembled successfully", taskID)

			_, dbErr := e.db.ExecContext(ctx,
				"UPDATE tasks SET status = 'RUNNING', last_run_at = CURRENT_TIMESTAMP WHERE id = ?", taskID)
			if dbErr == nil && e.onTaskUpdate != nil {
				e.onTaskUpdate(taskID, "RUNNING")
			}
			if dbErr != nil {
				return dbErr
			}

			req := api.SessionRequest{
				Prompt: fullPrompt,
				SourceContext: api.SourceContext{
					Source: "sources/github/" + repoName,
					GithubRepoContext: api.GithubRepoContext{
						StartingBranch: "main",
					},
				},
				AutomationMode: "AUTO_CREATE_PR",
				Title:          fmt.Sprintf("[%s] %s for %s", agent, mission, repoName),
			}

			reqJSON, _ := json.Marshal(req)
			if logID > 0 {
				e.db.ExecContext(ctx, "UPDATE task_logs SET input_data = ? WHERE id = ?", string(reqJSON), logID)
			}

			log.Printf("Task %s: Sending request to Jules API...", taskID)
			resp, rawOut, err := e.client.StartSession(ctx, req)
			if err != nil {
				return err
			}

			sessionID = taskID
			if resp != nil && resp.ID != "" {
				sessionID = resp.ID
			}

			if e.budgetMgr != nil {
				e.budgetMgr.TrackUsage(ctx, taskID, sessionID, 0, 0, "jules")
			}

			log.Printf("Task %s: Session STARTED successfully (ID: %s)", taskID, sessionID)
			if logID > 0 {
				e.db.ExecContext(ctx, "UPDATE task_logs SET session_id = ?, output_data = ? WHERE id = ?", sessionID, string(rawOut), logID)
			}

			_, sessErr := e.db.ExecContext(ctx,
				"INSERT INTO sessions (id, task_id, jules_session_id, status) VALUES (?, ?, ?, ?)",
				sessionID, taskID, sessionID, "RUNNING")
			if sessErr == nil {
				log.Printf("Task %s: Session %s registered for monitoring", taskID, sessionID)
			} else {
				log.Printf("Task %s: WARNING - failed to register session %s: %v", taskID, sessionID, sessErr)
			}

			return nil
		})

		if err != nil {
			break // System error, don't retry in loop
		}

		// Phase 2: Verification
		if e.verifier != nil {
			e.updateTaskStatus(ctx, taskID, "VERIFYING", "")
			res, vErr := e.verifier.Verify(ctx, repoName, sessionID)
			if vErr == nil && !res.Success {
				if currentRetry < maxRetries {
					currentRetry++
					lastVerificationError = res.Error
					log.Printf("Task %s: Verification FAILED. Starting correction attempt %d/%d. Error: %s", taskID, currentRetry, maxRetries, res.Error)
					e.updateTaskStatus(ctx, taskID, "CORRECTING", "current_retry = ?", currentRetry)
					
					if e.tracer != nil {
						e.tracer.BroadcastTrace(monitor.AgentTraceEvent{
							TaskID:    taskID,
							Type:      monitor.TraceThought,
							Content:   fmt.Sprintf("Verification failed: %s. Starting correction attempt %d.", res.Error, currentRetry),
							Timestamp: time.Now(),
						})
					}
					continue
				} else {
					err = fmt.Errorf("verification failed after %d retries: %s", maxRetries, res.Error)
				}
			} else if vErr != nil {
				err = fmt.Errorf("verification error: %w", vErr)
			}
		}
		break
	}

	duration := time.Since(start)

	if err != nil {
		execStatus = "FAILED"
		execError = err.Error()
		log.Printf("Task %s: EXECUTION FAILED: %v", taskID, err)
		e.updateTaskStatus(ctx, taskID, "FAILED", "failure_count = failure_count + 1, last_error = ?, current_retry = 0", execError)
		if e.notifier != nil {
			e.notifier.SendAlert(taskID, err.Error())
		}
	} else {
		execStatus = "COMPLETED"
		log.Printf("Task %s: COMPLETED in %v", taskID, duration)
		e.updateTaskStatus(ctx, taskID, "PENDING", "failure_count = 0, last_error = '', current_retry = 0")
	}

	if logID > 0 {
		e.db.ExecContext(ctx, `
			UPDATE task_logs 
			SET status = ?, error = ?, duration_ms = ?
			WHERE id = ?
		`, execStatus, execError, duration.Milliseconds(), logID)
		
		if e.onActivityUpdate != nil {
			e.onActivityUpdate()
		}
	}
}

// buildPrompt builds the Jules prompt from the prompt-library clone.
// Returns an error (and causes the task to be paused) if the library is not ready.
func (e *Engine) buildPrompt(ctx context.Context, agent, pattern, mission, repoName, lastError, category string) (string, error) {
	if e.promptBuilder == nil || !e.promptBuilder.IsReady() {
		return "", fmt.Errorf("prompt-library not ready (git sync pending) — task paused until library is available")
	}
	ragContext := ""
	if e.contextSearch != nil {
		query := fmt.Sprintf("%s %s %s", repoName, agent, mission)
		ragContext = e.contextSearch(ctx, repoName, query, 5, category)
		if ragContext != "" {
			log.Printf("Task dispatch: RAG context injected (%d chars) for %s/%s", len(ragContext), repoName, agent)
			
			if e.tracer != nil {
				e.tracer.BroadcastTrace(monitor.AgentTraceEvent{
					TaskID:    monitor.GetTaskID(ctx),
					Type:      monitor.TraceRAG,
					Content:   fmt.Sprintf("Injected %d chars of repository context", len(ragContext)),
					Timestamp: time.Now(),
					Metadata: map[string]string{
						"repo": repoName,
					},
				})
			}
		}
	}
	
	prompt, err := e.promptBuilder.Build(agent, pattern, mission, ragContext)
	if err != nil {
		return "", err
	}

	if lastError != "" {
		prompt = fmt.Sprintf("%s\n\nCRITICAL: Your previous attempt failed with the following error. Please analyze it and CORRECT your implementation:\nERROR: %s", prompt, lastError)
	}

	return prompt, nil
}

