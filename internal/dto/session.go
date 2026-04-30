package dto

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"time"

	_ "modernc.org/sqlite"
)

type DialogueMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type DialogueSession struct {
	RepoName     string            `json:"repo_name"`
	Context      []DialogueMessage `json:"context"`
	CurrentStage string            `json:"current_stage"`
	LLMProvider  string            `json:"llm_provider"` // "internal" or "external"
	Status       string            `json:"status"`       // "IDLE", "DIALOGUE"
	UpdatedAt    time.Time         `json:"updated_at"`
}

type SessionManager struct {
	db *sql.DB
}

func NewSessionManager(dbDir string) (*SessionManager, error) {
	if err := os.MkdirAll(dbDir, 0755); err != nil {
		return nil, fmt.Errorf("creating dto db directory: %w", err)
	}

	dbPath := filepath.Join(dbDir, "dto_sessions.db")
	db, err := sql.Open("sqlite", dbPath)
	if err != nil {
		return nil, fmt.Errorf("opening dto sessions db: %w", err)
	}

	// Optimize SQLite for concurrent access
	db.SetMaxOpenConns(1)
	if _, err := db.Exec("PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;"); err != nil {
		return nil, fmt.Errorf("configuring dto sessions db: %w", err)
	}

	schema := `
	CREATE TABLE IF NOT EXISTS dialogue_sessions (
		repo_name TEXT PRIMARY KEY,
		context TEXT,
		current_stage TEXT,
		llm_provider TEXT DEFAULT 'internal',
		status TEXT DEFAULT 'IDLE',
		updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
	);`

	if _, err := db.Exec(schema); err != nil {
		return nil, fmt.Errorf("initializing dto sessions schema: %w", err)
	}

	return &SessionManager{db: db}, nil
}

func (m *SessionManager) GetSession(ctx context.Context, repoName string) (*DialogueSession, error) {
	var ctxJson, currentStage, llmProvider, status string
	var updatedAt time.Time

	err := m.db.QueryRowContext(ctx, 
		"SELECT context, current_stage, llm_provider, status, updated_at FROM dialogue_sessions WHERE repo_name = ?", 
		repoName).Scan(&ctxJson, &currentStage, &llmProvider, &status, &updatedAt)

	if err == sql.ErrNoRows {
		return &DialogueSession{
			RepoName:     repoName,
			Context:      []DialogueMessage{},
			CurrentStage: "discovery",
			LLMProvider:  "internal",
			Status:       "IDLE",
			UpdatedAt:    time.Now(),
		}, nil
	} else if err != nil {
		return nil, err
	}

	var messages []DialogueMessage
	if ctxJson != "" {
		json.Unmarshal([]byte(ctxJson), &messages)
	}

	return &DialogueSession{
		RepoName:     repoName,
		Context:      messages,
		CurrentStage: currentStage,
		LLMProvider:  llmProvider,
		Status:       status,
		UpdatedAt:    updatedAt,
	}, nil
}

func (m *SessionManager) SaveSession(ctx context.Context, s *DialogueSession) error {
	ctxJson, _ := json.Marshal(s.Context)
	_, err := m.db.ExecContext(ctx, `
		INSERT INTO dialogue_sessions (repo_name, context, current_stage, llm_provider, status, updated_at)
		VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
		ON CONFLICT(repo_name) DO UPDATE SET
			context = excluded.context,
			current_stage = excluded.current_stage,
			llm_provider = excluded.llm_provider,
			status = excluded.status,
			updated_at = CURRENT_TIMESTAMP`,
		s.RepoName, string(ctxJson), s.CurrentStage, s.LLMProvider, s.Status)
	return err
}

func (m *SessionManager) AddMessage(ctx context.Context, repoName string, msg DialogueMessage) error {
	session, err := m.GetSession(ctx, repoName)
	if err != nil {
		return err
	}
	session.Context = append(session.Context, msg)
	session.Status = "DIALOGUE"
	return m.SaveSession(ctx, session)
}

func (m *SessionManager) ClearSession(ctx context.Context, repoName string) error {
	_, err := m.db.ExecContext(ctx, "DELETE FROM dialogue_sessions WHERE repo_name = ?", repoName)
	return err
}

func (m *SessionManager) Close() error {
	return m.db.Close()
}
