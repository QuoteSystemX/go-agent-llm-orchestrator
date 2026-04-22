package scheduler

import (
	"context"
	"log"
	"sync"

	"go-agent-llm-orchestrator/internal/api"
	"go-agent-llm-orchestrator/internal/db"
	"go-agent-llm-orchestrator/internal/notifier"
	"go-agent-llm-orchestrator/internal/traffic"
	"github.com/robfig/cron/v3"
)

type Engine struct {
	cron    *cron.Cron
	db      *db.DB
	tm      *traffic.TrafficManager
	client  *api.JulesClient
	notifier *notifier.TelegramNotifier
	mu      sync.Mutex
	entries map[string]cron.EntryID
}

func NewEngine(database *db.DB, tm *traffic.TrafficManager, client *api.JulesClient, nt *notifier.TelegramNotifier) *Engine {
	return &Engine{
		cron:    cron.New(),
		db:      database,
		tm:      tm,
		client:  client,
		notifier: nt,
		entries: make(map[string]cron.EntryID),
	}
}

func (e *Engine) Start() {
	e.cron.Start()
	log.Println("Scheduler engine started")
}

func (e *Engine) Stop() {
	e.cron.Stop()
}

// SyncTasks reads tasks from DB and updates the cron schedule
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

	// Remove tasks that are no longer in DB
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
		// We could fetch actual next run time from cron, but for now just ID and schedule
		// Fetching schedule string from entries map if we store it
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
	
	// Fetch task details for logging and execution
	var status, mission, pattern string
	err := e.db.QueryRowContext(ctx, "SELECT status, mission, pattern FROM tasks WHERE id = ?", taskID).Scan(&status, &mission, &pattern)
	if err != nil {
		log.Printf("Failed to fetch task %s details: %v", taskID, err)
		return
	}

	if status == "PAUSED" {
		log.Printf("Task %s is paused, skipping", taskID)
		return
	}

	var inputPayload, outputPayload []byte
	var execStatus string = "SUCCESS"
	var execError string

	err = e.tm.Execute(ctx, traffic.PriorityHigh, func() error {
		// 1. Update status to RUNNING
		_, err := e.db.ExecContext(ctx, "UPDATE tasks SET status = 'RUNNING', last_run_at = CURRENT_TIMESTAMP WHERE id = ?", taskID)
		if err != nil {
			return err
		}

		// 2. Call Jules API
		resp, rawIn, err := e.client.StartSession(ctx, taskID, mission, pattern)
		inputPayload = rawIn
		if err != nil {
			return err
		}
		
		// 3. Create session entry
		_, err = e.db.ExecContext(ctx, 
			"INSERT INTO sessions (id, task_id, jules_session_id, status) VALUES (?, ?, ?, ?)",
			resp.ID, taskID, resp.ID, "RUNNING")
		
		// For now we assume the immediate response body is what we want to log as "Out"
		// In a more complex setup, we'd poll for final result.
		// Wait, if it returns ID, it's just started. But user wants "In/Out".
		// Let's log the initial response for now.
		outputPayload, _ = json.Marshal(resp)
		
		return err
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

	// Record Execution Log
	_, logErr := e.db.ExecContext(ctx, `
		INSERT INTO task_logs (task_id, input_data, output_data, status, error, duration_ms)
		VALUES (?, ?, ?, ?, ?, ?)
	`, taskID, string(inputPayload), string(outputPayload), execStatus, execError, duration.Milliseconds())
	
	if logErr != nil {
		log.Printf("Failed to record log for task %s: %v", taskID, logErr)
	}
}
