package scheduler

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"strings"
	"sync"
	"time"

	"go-agent-llm-orchestrator/internal/api"
	"go-agent-llm-orchestrator/internal/db"
	"go-agent-llm-orchestrator/internal/llm"
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
	router        *llm.Router
	mu            sync.Mutex
	entries       map[string]cron.EntryID
}

func NewEngine(database *db.DB, tm *traffic.TrafficManager, client *api.JulesClient, nt *notifier.TelegramNotifier, pb *prompt.Builder, router *llm.Router) *Engine {
	return &Engine{
		cron:          cron.New(),
		db:            database,
		tm:            tm,
		client:        client,
		notifier:      nt,
		promptBuilder: pb,
		router:        router,
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
	var active []string
	for id := range e.entries {
		active = append(active, id)
	}
	log.Printf("Scheduler: %d tasks active: [%s]", len(active), strings.Join(active, ", "))
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

	var status, mission, pattern, agent, repoName, category string
	var importance int
	err := e.db.QueryRowContext(ctx,
		"SELECT status, mission, pattern, COALESCE(agent,''), name, importance, category FROM tasks WHERE id = ?", taskID,
	).Scan(&status, &mission, &pattern, &agent, &repoName, &importance, &category)
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

	err = e.tm.Execute(ctx, traffic.PriorityHigh, importance, category, func() error {
		if logID > 0 {
			e.db.ExecContext(ctx, "UPDATE task_logs SET status = 'PROMPTING' WHERE id = ?", logID)
		}
		// 1. Determine which model to use (with Self-Healing)
		var failureCount int
		e.db.QueryRow("SELECT failure_count FROM tasks WHERE id = ?", taskID).Scan(&failureCount)

		isComplex := category == "service"
		if failureCount >= 3 {
			log.Printf("Engine: [Self-Healing] Task %s failed %d times. Forcing REMOTE model.", taskID, failureCount)
			isComplex = true
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

		// Decision: Use Local Agentic Worker or Jules API
		if e.router != nil && e.db.GetSetting("llm_local_endpoint", "") != "" {
			return e.runAgenticLocalTask(ctx, taskID, agent, pattern, mission, repoName, importance, category, logID, fullPrompt, isComplex)
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
		e.db.ExecContext(ctx, "UPDATE tasks SET status = 'FAILED', failure_count = failure_count + 1 WHERE id = ?", taskID)
		if e.notifier != nil {
			e.notifier.SendAlert(taskID, err.Error())
		}
	} else {
		execStatus = "COMPLETED"
		log.Printf("Task %s: COMPLETED in %v", taskID, duration)
		e.db.ExecContext(ctx, "UPDATE tasks SET status = 'PENDING', failure_count = 0 WHERE id = ?", taskID)
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

func (e *Engine) runAgenticLocalTask(ctx context.Context, taskID, agent, pattern, mission, repoName string, importance int, category string, logID int64, fullPrompt string, forceComplex bool) error {
	log.Printf("Task %s: STARTING LOCAL AGENTIC PIPELINE (4 Phases)", taskID)
	var err error
	var result, audit string

	runWithRetry := func(phase string, prompt string, modelType llm.Classification) (string, error) {
		var lastErr error
		for i := 1; i <= 3; i++ {
			if i > 1 {
				log.Printf("Task %s: Retrying phase %s (attempt %d/3)...", taskID, phase, i)
				time.Sleep(time.Duration(i) * time.Second)
			}
			res, err := e.router.GenerateResponse(ctx, modelType, prompt)
			if err == nil {
				return res, nil
			}
			lastErr = err
		}
		return "", lastErr
	}

	runWithStreaming := func(phase string, prompt string, modelType llm.Classification, logID int64) (string, error) {
		if logID == 0 {
			// Fallback to non-streaming if no logID
			return runWithRetry(phase, prompt, modelType)
		}

		var fullContent string
		start := time.Now()
		
		// Create placeholder
		detailID, err := e.db.AddTaskRunDetail(ctx, logID, phase, "Thinking...", 0)
		if err != nil {
			return "", err
		}

		stream, err := e.router.GenerateChatStream(ctx, modelType, []map[string]string{{"role": "user", "content": prompt}}, "")
		if err != nil {
			return "", err
		}

		lastUpdate := time.Now()
		for chunk := range stream {
			fullContent += chunk
			if time.Since(lastUpdate) > 1*time.Second {
				e.db.UpdateTaskRunDetailContent(ctx, detailID, fullContent)
				lastUpdate = time.Now()
			}
		}

		duration := time.Since(start).Milliseconds()
		e.db.ExecContext(ctx, "UPDATE task_run_details SET content = ?, duration_ms = ? WHERE id = ?", fullContent, duration, detailID)
		
		return fullContent, nil
	}

	// Phase 1 & 2: ANALYSIS & PLANNING
	var analysis, plan string
	
	// Check if we have a pending decision to resume from
	var existingDecision string
	err = e.db.QueryRowContext(ctx, "SELECT pending_decision FROM tasks WHERE id = ?", taskID).Scan(&existingDecision)
	
	if err == nil && existingDecision != "" {
		log.Printf("Task %s: Resuming from PENDING DECISION", taskID)
		plan = existingDecision
		e.updateProgress(ctx, taskID, "execution", 60, logID)
	} else {
		// Phase 1: ANALYSIS
		e.updateProgress(ctx, taskID, "analysis", 25, logID)
		analysisPrompt := fmt.Sprintf("Phase 1: ANALYSIS. Mission: %s. Repository: %s. Prompt: %s. Analyze the requirements and constraints.", mission, repoName, fullPrompt)
		analysisModel := llm.Simple
		if forceComplex {
			analysisModel = llm.Complex
		}
		analysis, err = runWithStreaming("analysis", analysisPrompt, analysisModel, logID)
		if err != nil {
			return fmt.Errorf("analysis phase failed: %w", err)
		}

		// Phase 2: PLANNING
		e.updateProgress(ctx, taskID, "planning", 50, logID)
		planningPrompt := fmt.Sprintf("Phase 2: PLANNING. Context: %s. Based on the analysis, create a step-by-step plan.", analysis)
		planningModel := llm.Simple
		if forceComplex {
			planningModel = llm.Complex
		}
		plan, err = runWithStreaming("planning", planningPrompt, planningModel, logID)
		if err != nil {
			return fmt.Errorf("planning phase failed: %w", err)
		}

		// Check if human approval is required
		var approvalReq int
		e.db.QueryRowContext(ctx, "SELECT approval_required FROM tasks WHERE id = ?", taskID).Scan(&approvalReq)
		if approvalReq == 1 {
			log.Printf("Task %s: PAUSING FOR HUMAN APPROVAL", taskID)
			e.db.ExecContext(ctx, "UPDATE tasks SET status = 'WAITING', pending_decision = ? WHERE id = ?", plan, taskID)
			if logID > 0 {
				e.db.ExecContext(ctx, "UPDATE task_logs SET status = 'AWAITING_APPROVAL' WHERE id = ?", logID)
			}
			return nil // Pause execution here
		}
	}

	// Phase 3: EXECUTION
	e.updateProgress(ctx, taskID, "execution", 75, logID)
	execPrompt := fmt.Sprintf("Phase 3: EXECUTION. Mission: %s. Plan: %s. Implement the task and provide the final output.", mission, plan)
	result, err = runWithStreaming("execution", execPrompt, llm.Complex, logID)
	if err != nil {
		return fmt.Errorf("execution phase failed: %w", err)
	}

	// Phase 4: VERIFICATION
	e.updateProgress(ctx, taskID, "verification", 100, logID)
	verifyPrompt := fmt.Sprintf("Phase 4: VERIFICATION. Original Mission: %s. Result: %s. Review the result for correctness and security.", mission, result)
	audit, err = runWithStreaming("verification", verifyPrompt, llm.Simple, logID)
	if err != nil {
		return fmt.Errorf("verification phase failed: %w", err)
	}

	// Clear pending decision upon success
	e.db.ExecContext(ctx, "UPDATE tasks SET pending_decision = '' WHERE id = ?", taskID)

	log.Printf("Task %s: LOCAL AGENTIC PIPELINE COMPLETED", taskID)
	if logID > 0 {
		e.db.ExecContext(ctx, "UPDATE task_logs SET output_data = ? WHERE id = ?", fmt.Sprintf("RESULT:\n%s\n\nAUDIT:\n%s", result, audit), logID)
	}

	return nil
}

func (e *Engine) updateProgress(ctx context.Context, taskID string, stage string, progress int, logID int64) {
	e.db.UpdateTaskProgress(ctx, taskID, stage, progress)
	if logID > 0 {
		e.db.ExecContext(ctx, "UPDATE task_logs SET status = ? WHERE id = ?", fmt.Sprintf("PHASE: %s", strings.ToUpper(stage)), logID)
	}
}
