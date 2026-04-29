package llm

import (
	"context"
	"fmt"
	"log"

	"go-agent-llm-orchestrator/internal/db"
	"go-agent-llm-orchestrator/internal/traffic"
)

const defaultSupervisorPrompt = `Analyze this blocked session: %s. Task: %s. Provide a decision to unblock.`

// JulesClientIface is the subset of JulesClient the Supervisor needs.
// api.JulesClient satisfies this interface via duck typing.
type JulesClientIface interface {
	GetSession(ctx context.Context, sessionID string) (*db.SessionInfo, error)
	SendMessage(ctx context.Context, sessionID, prompt string) error
	ApprovePlan(ctx context.Context, sessionID string) error
}

type Supervisor struct {
	db          *db.DB
	tm          *traffic.TrafficManager
	router      *Router
	julesClient JulesClientIface
}

func NewSupervisor(database *db.DB, tm *traffic.TrafficManager, router *Router, client JulesClientIface) *Supervisor {
	return &Supervisor{
		db:          database,
		tm:          tm,
		router:      router,
		julesClient: client,
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

	// 1. Look up task context from local DB — no Jules API call needed.
	taskDesc := "unknown task"
	sessionStatus := ""
	var mission string
	err := s.db.QueryRowContext(ctx, `
		SELECT s.status, COALESCE(t.mission, '')
		FROM sessions s
		LEFT JOIN tasks t ON t.id = s.task_id
		WHERE s.jules_session_id = ?`, sessionID).Scan(&sessionStatus, &mission)
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

	// 4. Post response to Jules API
	err = s.tm.Execute(ctx, sessionID, traffic.PriorityHigh, 5, "service", func() error {
		if sessionStatus == "AWAITING_PLAN_APPROVAL" {
			log.Printf("Approving plan for session %s", sessionID)
			return s.julesClient.ApprovePlan(ctx, sessionID)
		}
		log.Printf("Sending message to session %s: %s", sessionID, response)
		return s.julesClient.SendMessage(ctx, sessionID, response)
	})
	if err != nil {
		return fmt.Errorf("posting to Jules API failed: %v", err)
	}

	// 5. Audit log
	details := fmt.Sprintf("Class: %s | Status: %s | Response: %s", class, sessionStatus, response)
	_, err = s.db.History().ExecContext(ctx,
		"INSERT INTO audit_logs (session_id, action, details) VALUES (?, ?, ?)",
		sessionID, "AUTO_RESPONDED", details)
	return err
}
