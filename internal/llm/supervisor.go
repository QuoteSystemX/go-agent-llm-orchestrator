package llm

import (
	"context"
	"fmt"
	"log"

	"go-agent-llm-orchestrator/internal/db"
	"go-agent-llm-orchestrator/internal/traffic"
)

type Supervisor struct {
	db     *db.DB
	tm     *traffic.TrafficManager
	router *Router
}

func NewSupervisor(database *db.DB, tm *traffic.TrafficManager, router *Router) *Supervisor {
	return &Supervisor{
		db:     database,
		tm:     tm,
		router: router,
	}
}

func (s *Supervisor) RespondToBlock(ctx context.Context, sessionID string) error {
	log.Printf("Supervising blocked session %s", sessionID)

	// In a real scenario, we would fetch session history here.
	// For now, we use a placeholder task description for classification.
	taskDesc := "Agent is asking for permission to refactor the database schema for the notifier module."
	
	// 1. Classify task (Local LLM)
	class, err := s.router.Classify(ctx, taskDesc)
	if err != nil {
		return fmt.Errorf("classification failed: %v", err)
	}

	// 2. Generate response (Local or Remote LLM based on class)
	prompt := fmt.Sprintf("Analyze this blocked session: %s. Task: %s. Provide a decision to unblock.", sessionID, taskDesc)
	response, err := s.router.GenerateResponse(ctx, class, prompt)
	if err != nil {
		return fmt.Errorf("response generation failed: %v", err)
	}

	// 3. Post response to Jules API via TrafficManager
	err = s.tm.Execute(ctx, traffic.PriorityHigh, func() error {
		log.Printf("Posting auto-response (%s) to session %s: %s", class, sessionID, response)
		return nil
	})
	if err != nil {
		return err
	}

	// 4. Log to audit_logs with details
	details := fmt.Sprintf("Class: %s | Prompt: %s | Response: %s", class, prompt, response)
	_, err = s.db.ExecContext(ctx, 
		"INSERT INTO audit_logs (session_id, action, details) VALUES (?, ?, ?)",
		sessionID, "AUTO_RESPONDED", details)
	
	return err
}
