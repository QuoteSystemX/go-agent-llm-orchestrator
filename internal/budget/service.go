package budget

import (
	"context"
	"database/sql"
	"fmt"
	"log"

	"go-agent-llm-orchestrator/internal/db"
)

type Pricing struct {
	Model          string
	InputPer1M     float64
	OutputPer1M    float64
	IsSessionBased bool
}

var DefaultPricing = map[string]Pricing{
	"gpt-4o": {
		Model:       "gpt-4o",
		InputPer1M:  2.50,
		OutputPer1M: 10.00,
	},
	"claude-3-5-sonnet": {
		Model:       "claude-3-5-sonnet",
		InputPer1M:  3.00,
		OutputPer1M: 15.00,
	},
	"gemini-1-5-pro": {
		Model:       "gemini-1-5-pro",
		InputPer1M:  1.25,
		OutputPer1M: 5.00,
	},
}

type Budget struct {
	ID                  int     `json:"id"`
	TargetType          string  `json:"target_type"`
	TargetID            string  `json:"target_id"`
	DailySessionLimit   int     `json:"daily_session_limit"`
	MonthlyCostLimit    float64 `json:"monthly_cost_limit"`
	AlertThreshold      float64 `json:"alert_threshold"`
}

type Manager struct {
	db *db.DB
}

func NewManager(database *db.DB) *Manager {
	return &Manager{db: database}
}

func (m *Manager) CalculateCost(model string, inputTokens, outputTokens int) float64 {
	p, ok := DefaultPricing[model]
	if !ok {
		return 0
	}
	if p.IsSessionBased {
		return 0
	}
	inputCost := (float64(inputTokens) / 1_000_000.0) * p.InputPer1M
	outputCost := (float64(outputTokens) / 1_000_000.0) * p.OutputPer1M
	return inputCost + outputCost
}

func (m *Manager) TrackUsage(ctx context.Context, taskID, julesSessionID string, promptTokens, completionTokens int, model string) error {
	cost := m.CalculateCost(model, promptTokens, completionTokens)
	totalTokens := promptTokens + completionTokens

	_, err := m.db.History().ExecContext(ctx, `
		UPDATE task_logs 
		SET jules_session_id = ?, 
		    prompt_tokens = ?, 
		    completion_tokens = ?, 
		    total_tokens = ?, 
		    cost_usd = ?
		WHERE id = (SELECT MAX(id) FROM task_logs WHERE task_id = ?)
	`, julesSessionID, promptTokens, completionTokens, totalTokens, cost, taskID)
	
	if err != nil {
		log.Printf("Failed to track usage: %v", err)
	}
	return err
}

func (m *Manager) CheckBudget(ctx context.Context, targetID string) (bool, error) {
	var dailyLimit int
	var monthlyLimit float64
	err := m.db.Main().QueryRowContext(ctx, `
		SELECT daily_session_limit, monthly_cost_limit 
		FROM budgets 
		WHERE target_type = 'system' OR target_id = ?
		ORDER BY target_type DESC LIMIT 1
	`, targetID).Scan(&dailyLimit, &monthlyLimit)
	
	if err == sql.ErrNoRows {
		dailyLimit = 100
		monthlyLimit = 50.0
	} else if err != nil {
		return false, err
	}

	var sessionsToday int
	m.db.History().QueryRowContext(ctx, `
		SELECT COUNT(DISTINCT jules_session_id) 
		FROM task_logs 
		WHERE executed_at >= date('now') AND jules_session_id != ''
	`).Scan(&sessionsToday)

	if sessionsToday >= dailyLimit {
		return false, fmt.Errorf("daily session limit reached (%d/%d)", sessionsToday, dailyLimit)
	}

	var costThisMonth float64
	m.db.History().QueryRowContext(ctx, `
		SELECT SUM(cost_usd) 
		FROM task_logs 
		WHERE executed_at >= date('now', 'start of month')
	`).Scan(&costThisMonth)

	if costThisMonth >= monthlyLimit {
		return false, fmt.Errorf("monthly cost limit reached ($%.2f/$%.2f)", costThisMonth, monthlyLimit)
	}

	return true, nil
}

func (m *Manager) GetSummary(ctx context.Context) (map[string]any, error) {
	var dailyLimit int
	var monthlyLimit float64
	err := m.db.Main().QueryRowContext(ctx, `
		SELECT daily_session_limit, monthly_cost_limit 
		FROM budgets 
		WHERE target_type = 'system'
		LIMIT 1
	`).Scan(&dailyLimit, &monthlyLimit)
	if err == sql.ErrNoRows {
		dailyLimit = 100
		monthlyLimit = 50.0
	} else if err != nil && err != sql.ErrNoRows {
		return nil, err
	}

	var sessionsToday int
	m.db.History().QueryRowContext(ctx, `
		SELECT COUNT(DISTINCT jules_session_id) 
		FROM task_logs 
		WHERE executed_at >= date('now') AND jules_session_id != ''
	`).Scan(&sessionsToday)

	var costThisMonth float64
	m.db.History().QueryRowContext(ctx, `
		SELECT COALESCE(SUM(cost_usd), 0)
		FROM task_logs 
		WHERE executed_at >= date('now', 'start of month')
	`).Scan(&costThisMonth)

	return map[string]any{
		"daily_sessions_used":  sessionsToday,
		"daily_sessions_limit": dailyLimit,
		"monthly_cost_usd":     costThisMonth,
		"monthly_cost_limit":   monthlyLimit,
	}, nil
}

func (m *Manager) ListBudgets(ctx context.Context) ([]Budget, error) {
	rows, err := m.db.Main().QueryContext(ctx, "SELECT id, target_type, COALESCE(target_id, ''), daily_session_limit, monthly_cost_limit, alert_threshold FROM budgets")
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var res []Budget
	for rows.Next() {
		var b Budget
		if err := rows.Scan(&b.ID, &b.TargetType, &b.TargetID, &b.DailySessionLimit, &b.MonthlyCostLimit, &b.AlertThreshold); err != nil {
			return nil, err
		}
		res = append(res, b)
	}
	return res, nil
}

func (m *Manager) UpsertBudget(ctx context.Context, b Budget) error {
	_, err := m.db.Main().ExecContext(ctx, `
		INSERT INTO budgets (target_type, target_id, daily_session_limit, monthly_cost_limit, alert_threshold)
		VALUES (?, ?, ?, ?, ?)
		ON CONFLICT(target_type, target_id) DO UPDATE SET
			daily_session_limit = excluded.daily_session_limit,
			monthly_cost_limit = excluded.monthly_cost_limit,
			alert_threshold = excluded.alert_threshold
	`, b.TargetType, b.TargetID, b.DailySessionLimit, b.MonthlyCostLimit, b.AlertThreshold)
	return err
}
