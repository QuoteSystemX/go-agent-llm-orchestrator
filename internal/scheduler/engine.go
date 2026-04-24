package scheduler

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"sync"
	"time"

	"go-agent-llm-orchestrator/internal/api"
	"go-agent-llm-orchestrator/internal/db"
	"go-agent-llm-orchestrator/internal/notifier"
	"go-agent-llm-orchestrator/internal/prompt"
	"go-agent-llm-orchestrator/internal/traffic"
	"github.com/robfig/cron/v3"
)

type Engine struct {
	cron          *cron.Cron
	db            *db.DB
	tm            *traffic.TrafficManager
	client        *api.JulesClient
	notifier      *notifier.TelegramNotifier
	promptBuilder *prompt.Builder
	mu            sync.Mutex
	entries       map[string]cron.EntryID
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
	}
}

func (e *Engine) Start() {
	e.cron.Start()
	log.Println("Scheduler engine started")
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

func (e *Engine) TriggerTask(taskID string) {
	log.Printf("Manual trigger for task %s", taskID)
	go e.runTask(taskID)
}

func (e *Engine) SyncTasks(ctx context.Context) error {
	e.mu.Lock()
	defer e.mu.Unlock()

	rows, err := e.db.QueryContext(ctx, "SELECT id, schedule FROM tasks")
	if err != nil {
		return err
	}
	defer rows.Close()

	activeIDs := make(map[string]bool)
	addedCount := 0

	for rows.Next() {
		var id, schedule string
		if err := rows.Scan(&id, &schedule); err != nil {
			continue
		}
		activeIDs[id] = true

		if _, exists := e.entries[id]; !exists {
			if err := e.addTask(id, schedule); err != nil {
				log.Printf("Failed to add task %s: %v", id, err)
			} else {
				addedCount++
			}
		}
	}

	removedCount := 0
	for id, entryID := range e.entries {
		if !activeIDs[id] {
			e.cron.Remove(entryID)
			delete(e.entries, id)
			log.Printf("Removed task %s from scheduler", id)
			removedCount++
		}
	}

	if addedCount > 0 || removedCount > 0 {
		e.printSchedule()
	}

	return nil
}

func (e *Engine) printSchedule() {
	log.Println("┌─────────────────────────────────────────────────────────────────┐")
	log.Println("│ CURRENT AGENT SCHEDULE                                          │")
	log.Println("├──────────────────────────┬──────────────────────────────────────┤")
	log.Println("│ TASK ID                  │ CRON EXPRESSION                      │")
	log.Println("├──────────────────────────┼──────────────────────────────────────┤")
	for id := range e.entries {
		log.Printf("│ %-24s │ (scheduled)                          │", id)
	}
	log.Println("└──────────────────────────┴──────────────────────────────────────┘")
}

func (e *Engine) addTask(id, schedule string) error {
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

func (e *Engine) runTask(taskID string) {
	log.Printf("Task %s: TRIGGERED", taskID)

	ctx := context.Background()
	start := time.Now()

	var status, mission, pattern, agent, repoName string
	err := e.db.QueryRowContext(ctx,
		"SELECT status, mission, pattern, COALESCE(agent,''), name FROM tasks WHERE id = ?", taskID,
	).Scan(&status, &mission, &pattern, &agent, &repoName)
	if err != nil {
		log.Printf("Task %s: FAILED to fetch from DB: %v", taskID, err)
		return
	}

	if status == "PAUSED" {
		log.Printf("Task %s: SKIPPED (status is PAUSED)", taskID)
		return
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

	err = e.tm.Execute(ctx, traffic.PriorityHigh, func() error {
		if logID > 0 {
			e.db.ExecContext(ctx, "UPDATE task_logs SET status = 'PROMPTING' WHERE id = ?", logID)
		}
		// Build the full Jules prompt — pause the task if library is not ready yet
		fullPrompt, err := e.buildPrompt(agent, pattern, mission)
		if err != nil {
			e.db.ExecContext(ctx, "UPDATE tasks SET status = 'PAUSED', auto_paused = 1 WHERE id = ?", taskID)
			if logID > 0 {
				e.db.ExecContext(ctx, "UPDATE task_logs SET status = 'FAILED', error = ? WHERE id = ?", err.Error(), logID)
			}
			return fmt.Errorf("prompt-library not ready, task %s paused: %w", taskID, err)
		}
		log.Printf("Task %s: Prompt assembled successfully", taskID)

		_, dbErr := e.db.ExecContext(ctx,
			"UPDATE tasks SET status = 'RUNNING', last_run_at = CURRENT_TIMESTAMP WHERE id = ?", taskID)
		if dbErr != nil {
			return dbErr
		}

		if logID > 0 {
			e.db.ExecContext(ctx, "UPDATE task_logs SET status = 'EXECUTING' WHERE id = ?", logID)
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

	duration := time.Since(start)

	if err != nil {
		execStatus = "FAILED"
		execError = err.Error()
		log.Printf("Task %s: EXECUTION FAILED: %v", taskID, err)
		e.db.ExecContext(ctx, "UPDATE tasks SET status = 'FAILED' WHERE id = ?", taskID)
		if e.notifier != nil {
			e.notifier.SendAlert(taskID, err.Error())
		}
	} else {
		execStatus = "COMPLETED"
		log.Printf("Task %s: COMPLETED in %v", taskID, duration)
		e.db.ExecContext(ctx, "UPDATE tasks SET status = 'PENDING' WHERE id = ?", taskID)
	}

	if logID > 0 {
		e.db.ExecContext(ctx, `
			UPDATE task_logs 
			SET status = ?, error = ?, duration_ms = ?
			WHERE id = ?
		`, execStatus, execError, duration.Milliseconds(), logID)
	}
}

// buildPrompt builds the Jules prompt from the prompt-library clone.
// Returns an error (and causes the task to be paused) if the library is not ready.
func (e *Engine) buildPrompt(agent, pattern, mission string) (string, error) {
	if e.promptBuilder != nil && e.promptBuilder.IsReady() {
		return e.promptBuilder.Build(agent, pattern, mission)
	}
	return "", fmt.Errorf("prompt-library not ready (git sync pending) — task paused until library is available")
}
