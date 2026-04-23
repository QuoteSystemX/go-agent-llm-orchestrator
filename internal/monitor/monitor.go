package monitor

import (
	"context"
	"fmt"
	"log"
	"strings"
	"time"

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

type Monitor struct {
	db          *db.DB
	tm          *traffic.TrafficManager
	julesClient JulesClientIface
	supervisor  SupervisorIface
}

func NewMonitor(database *db.DB, tm *traffic.TrafficManager, client JulesClientIface, sup SupervisorIface) *Monitor {
	return &Monitor{
		db:          database,
		tm:          tm,
		julesClient: client,
		supervisor:  sup,
	}
}

func (m *Monitor) Start(ctx context.Context, interval time.Duration) {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	log.Printf("Status monitor started (interval: %v)", interval)

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			if err := m.pollStatuses(ctx); err != nil {
				log.Printf("Error polling statuses: %v", err)
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

func (m *Monitor) pollStatuses(ctx context.Context) error {
	rows, err := m.db.QueryContext(ctx,
		`SELECT id, jules_session_id, status FROM sessions
		 WHERE status NOT IN ('COMPLETED','FAILED') AND jules_session_id != ''`)
	if err != nil {
		return fmt.Errorf("querying sessions: %w", err)
	}

	type sessionRow struct {
		id, julesSessionID, status string
	}
	var activeSessions []sessionRow
	for rows.Next() {
		var s sessionRow
		if err := rows.Scan(&s.id, &s.julesSessionID, &s.status); err != nil {
			continue
		}
		activeSessions = append(activeSessions, s)
	}
	rows.Close()

	if len(activeSessions) == 0 {
		return nil
	}

	triggerSet := make(map[string]bool)
	for _, s := range m.getTriggerStatuses() {
		triggerSet[s] = true
	}

	for _, sess := range activeSessions {
		sess := sess
		m.tm.Execute(ctx, traffic.PriorityLow, func() error {
			newStatus, err := m.julesClient.GetStatus(ctx, sess.julesSessionID)
			if err != nil {
				log.Printf("Failed to get status for session %s: %v", sess.julesSessionID, err)
				return nil
			}

			m.db.ExecContext(ctx,
				"UPDATE sessions SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
				newStatus, sess.id)

			if triggerSet[newStatus] && newStatus != sess.status {
				log.Printf("Session %s entered trigger status %s, invoking supervisor", sess.julesSessionID, newStatus)
				if err := m.supervisor.RespondToBlock(ctx, sess.julesSessionID); err != nil {
					log.Printf("Supervisor failed for session %s: %v", sess.julesSessionID, err)
				}
			}
			return nil
		})
	}
	return nil
}
