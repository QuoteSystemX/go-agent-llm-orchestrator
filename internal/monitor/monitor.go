package monitor

import (
	"context"
	"log"
	"time"

	"go-agent-llm-orchestrator/internal/db"
	"go-agent-llm-orchestrator/internal/traffic"
)

type Monitor struct {
	db *db.DB
	tm *traffic.TrafficManager
}

func NewMonitor(database *db.DB, tm *traffic.TrafficManager) *Monitor {
	return &Monitor{
		db: database,
		tm: tm,
	}
}

// Start begins the background polling process
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

func (m *Monitor) pollStatuses(ctx context.Context) error {
	// 1. Fetch active sessions from DB
	// 2. For each session, call Jules API (via tm.Execute with PriorityLow)
	// 3. Update status in DB (e.g., COMPLETED, BLOCKED)
	
	err := m.tm.Execute(ctx, traffic.PriorityLow, func() error {
		// Mock API call to Jules
		// log.Println("Polling Jules API for session statuses...")
		return nil
	})

	return err
}
