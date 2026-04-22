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

	for rows.Next() {
		var id, schedule string
		if err := rows.Scan(&id, &schedule); err != nil {
			continue
		}
		activeIDs[id] = true

		if _, exists := e.entries[id]; !exists {
			if err := e.addTask(id, schedule); err != nil {
				log.Printf("Failed to add task %s: %v", id, err)
			}
		}
	}

	// Remove tasks that are no longer in DB
	for id, entryID := range e.entries {
		if !activeIDs[id] {
			e.cron.Remove(entryID)
			delete(e.entries, id)
			log.Printf("Removed task %s from scheduler", id)
		}
	}

	return nil
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
	
	// Check if paused
	var status string
	err := e.db.QueryRowContext(ctx, "SELECT status FROM tasks WHERE id = ?", taskID).Scan(&status)
	if err == nil && status == "PAUSED" {
		log.Printf("Task %s is paused, skipping", taskID)
		return
	}

	err = e.tm.Execute(ctx, traffic.PriorityHigh, func() error {
		// 1. Update status to RUNNING
		_, err := e.db.ExecContext(ctx, "UPDATE tasks SET status = 'RUNNING', last_run_at = CURRENT_TIMESTAMP WHERE id = ?", taskID)
		if err != nil {
			return err
		}

		// 2. Call Jules API
		resp, err := e.client.StartSession(ctx, taskID)
		if err != nil {
			return err
		}

		// 3. Create session entry
		_, err = e.db.ExecContext(ctx, 
			"INSERT INTO sessions (id, task_id, jules_session_id, status) VALUES (?, ?, ?, ?)",
			resp.ID, taskID, resp.ID, "RUNNING")
		
		return err
	})

	if err != nil {
		log.Printf("Failed to run task %s: %v", taskID, err)
		e.db.ExecContext(ctx, "UPDATE tasks SET status = 'FAILED' WHERE id = ?", taskID)
		if e.notifier != nil {
			e.notifier.SendAlert(taskID, err.Error())
		}
	}
}
