package llm

import (
	"context"
	"fmt"
	"log"
	"go-agent-llm-orchestrator/internal/db"
	"go-agent-llm-orchestrator/internal/traffic"
)

const defaultSupervisorPrompt = `Analyze this blocked session: %s. Task: %s. Provide a decision to unblock.`

type Supervisor struct {
	db          *db.DB
	tm          *traffic.TrafficManager
	router      *Router
}

func NewSupervisor(database *db.DB, tm *traffic.TrafficManager, router *Router) *Supervisor {
	return &Supervisor{
		db:          database,
		tm:          tm,
		router:      router,
	}
}

func (s *Supervisor) getSupervisorPrompt() string {
	var val string
	if err := s.db.QueryRow("SELECT value FROM settings WHERE key = 'prompt_supervisor'").Scan(&val); err != nil || val == "" {
		return defaultSupervisorPrompt
	}
	return val
}

func (s *Supervisor) RespondToBlock(ctx context.Context, sessionID string) error {
	log.Printf("Supervising blocked session %s", sessionID)

	// 1. Look up task context from local DB
	taskDesc := "unknown task"
	sessionStatus := ""
	var mission string
	err := s.db.QueryRowContext(ctx, `
		SELECT s.status, COALESCE(t.mission, '')
		FROM sessions s
		LEFT JOIN tasks t ON t.id = s.task_id
		WHERE s.id = ?`, sessionID).Scan(&sessionStatus, &mission)
	if err != nil {
		log.Printf("Supervisor: could not find session %s in local DB: %v", sessionID, err)
	} else if mission != "" {
		taskDesc = mission
		log.Printf("Supervisor: session %s task=%q status=%s", sessionID, taskDesc, sessionStatus)
	}

	// 2. Classify task
	class, err := s.router.Classify(ctx, taskDesc)
	if err != nil {
		return fmt.Errorf("classification failed: %v", err)
	}

	// 3. Generate response using DB-backed prompt template
	prompt := fmt.Sprintf(s.getSupervisorPrompt(), sessionID, taskDesc)
	response, err := s.router.GenerateResponse(ctx, class, prompt)
	if err != nil {
		return fmt.Errorf("response generation failed: %v", err)
	}

	// 4. In autonomous mode, the supervisor should probably interact with the LocalExecutor
	// or update task status/metadata to unblock the loop.
	// For now, we just log it and record in audit history.
	log.Printf("Supervisor (Autonomous): Suggested action for %s: %s", sessionID, response)

	// 5. Audit log
	details := fmt.Sprintf("Class: %s | Status: %s | Suggestion: %s", class, sessionStatus, response)
	_, err = s.db.ExecContext(ctx,
		"INSERT INTO audit_logs (session_id, action, details) VALUES (?, ?, ?)",
		sessionID, "AUTO_SUPERVISED", details)
	return err
}
