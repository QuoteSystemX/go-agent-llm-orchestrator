package monitor

import (
	"context"
	"fmt"
	"log"
	"strings"

	"go-agent-llm-orchestrator/internal/db"
	"go-agent-llm-orchestrator/internal/traffic"
)

// JulesClientIface is the subset of api.JulesClient the Monitor needs.
type JulesClientIface interface {
	GetStatus(ctx context.Context, sessionID string) (string, error)
}

// SupervisorIface is the subset of llm.Supervisor the Monitor needs.
type SupervisorIface interface {
	RespondToBlock(ctx context.Context, sessionID string) error
}

type WebhookEvent struct {
	Event     string `json:"event"`
	SessionID string `json:"session_id"`
	TaskID    string `json:"task_id"`
	Status    string `json:"status"`
	Timestamp string `json:"timestamp"`
}

type Monitor struct {
	db          *db.DB
	tm          *traffic.TrafficManager
	julesClient JulesClientIface
	supervisor  SupervisorIface
	EventBus    chan WebhookEvent
	notifyFunc  func(taskID, status string)
}

func NewMonitor(database *db.DB, tm *traffic.TrafficManager, client JulesClientIface, sup SupervisorIface) *Monitor {
	return &Monitor{
		db:          database,
		tm:          tm,
		julesClient: client,
		supervisor:  sup,
		EventBus:    make(chan WebhookEvent, 100),
	}
}

func (m *Monitor) SetNotifyFunc(fn func(taskID, status string)) {
	m.notifyFunc = fn
}


func (m *Monitor) Start(ctx context.Context) {
	log.Println("Status monitor started (event-driven)")

	for {
		select {
		case <-ctx.Done():
			return
		case event := <-m.EventBus:
			if err := m.processEvent(ctx, event); err != nil {
				log.Printf("Error processing webhook event for session %s: %v", event.SessionID, err)
			}
		}
	}
}

func (m *Monitor) getTriggerStatuses() []string {
	var val string
	if err := m.db.QueryRow("SELECT value FROM settings WHERE key = 'trigger_statuses'").Scan(&val); err != nil || val == "" {
		return []string{"AWAITING_USER_FEEDBACK", "AWAITING_PLAN_APPROVAL"}
	}
	parts := strings.Split(val, ",")
	result := make([]string, 0, len(parts))
	for _, p := range parts {
		if s := strings.TrimSpace(p); s != "" {
			result = append(result, s)
		}
	}
	return result
}

func (m *Monitor) processEvent(ctx context.Context, event WebhookEvent) error {
	if event.SessionID == "" || event.Status == "" {
		return nil
	}

	// Fetch current status from DB to compare
	var currentStatus string
	var id string
	err := m.db.QueryRowContext(ctx, "SELECT id, status FROM sessions WHERE jules_session_id = ?", event.SessionID).Scan(&id, &currentStatus)
	if err != nil {
		// Session might not exist or we haven't tracked it yet
		return fmt.Errorf("session not found in db: %w", err)
	}

	// Update DB
	_, err = m.db.ExecContext(ctx, "UPDATE sessions SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", event.Status, id)
	if err != nil {
		return fmt.Errorf("updating session: %w", err)
	}

	triggerSet := make(map[string]bool)
	for _, s := range m.getTriggerStatuses() {
		triggerSet[s] = true
	}

	if event.Status != currentStatus {
		if m.notifyFunc != nil {
			// Find the task ID associated with this session to notify the UI
			var taskID string
			if err := m.db.QueryRowContext(ctx, "SELECT task_id FROM sessions WHERE id = ?", id).Scan(&taskID); err == nil {
				m.notifyFunc(taskID, event.Status)
			}
		}

		if triggerSet[event.Status] {
			log.Printf("Session %s entered trigger status %s, invoking supervisor", event.SessionID, event.Status)
			// Execute supervisor logic via traffic manager
			m.tm.Execute(ctx, traffic.PriorityLow, 0, "", func() error {
				if err := m.supervisor.RespondToBlock(ctx, event.SessionID); err != nil {
					log.Printf("Supervisor failed for session %s: %v", event.SessionID, err)
				}
				return nil
			})
		}
	}
	return nil
}

