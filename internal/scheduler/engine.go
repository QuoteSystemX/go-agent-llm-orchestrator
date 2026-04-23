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
	log.Printf("Triggering task %s", taskID)

	ctx := context.Background()
	start := time.Now()

	var status, mission, pattern, agent, repoName string
	err := e.db.QueryRowContext(ctx,
		"SELECT status, mission, pattern, COALESCE(agent,''), name FROM tasks WHERE id = ?", taskID,
	).Scan(&status, &mission, &pattern, &agent, &repoName)
	if err != nil {
		log.Printf("Failed to fetch task %s: %v", taskID, err)
		return
	}

	if status == "PAUSED" {
		log.Printf("Task %s is paused, skipping", taskID)
		return
	}

	var inputPayload, outputPayload []byte
	execStatus := "SUCCESS"
	var execError string

	err = e.tm.Execute(ctx, traffic.PriorityHigh, func() error {
		// Build the full Jules prompt — pause the task if library is not ready yet
		fullPrompt, err := e.buildPrompt(agent, pattern, mission)
		if err != nil {
			e.db.ExecContext(ctx, "UPDATE tasks SET status = 'PAUSED', auto_paused = 1 WHERE id = ?", taskID)
			return fmt.Errorf("prompt-library not ready, task %s paused: %w", taskID, err)
		}

		_, dbErr := e.db.ExecContext(ctx,
			"UPDATE tasks SET status = 'RUNNING', last_run_at = CURRENT_TIMESTAMP WHERE id = ?", taskID)
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
		inputPayload = reqJSON

		resp, rawOut, err := e.client.StartSession(ctx, req)
		if err != nil {
			return err
		}

		sessionID := taskID
		if resp != nil && resp.ID != "" {
			sessionID = resp.ID
		}
		outputPayload = rawOut

		e.db.ExecContext(ctx,
			"INSERT INTO sessions (id, task_id, jules_session_id, status) VALUES (?, ?, ?, ?)",
			sessionID, taskID, sessionID, "RUNNING")

		return nil
	})

	duration := time.Since(start)

	if err != nil {
		execStatus = "FAILED"
		execError = err.Error()
		log.Printf("Failed to run task %s: %v", taskID, err)
		e.db.ExecContext(ctx, "UPDATE tasks SET status = 'FAILED' WHERE id = ?", taskID)
		if e.notifier != nil {
			e.notifier.SendAlert(taskID, err.Error())
		}
	} else {
		e.db.ExecContext(ctx, "UPDATE tasks SET status = 'PENDING' WHERE id = ?", taskID)
	}

	_, logErr := e.db.ExecContext(ctx, `
		INSERT INTO task_logs (task_id, input_data, output_data, status, error, duration_ms)
		VALUES (?, ?, ?, ?, ?, ?)
	`, taskID, string(inputPayload), string(outputPayload), execStatus, execError, duration.Milliseconds())

	if logErr != nil {
		log.Printf("Failed to record log for task %s: %v", taskID, logErr)
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
