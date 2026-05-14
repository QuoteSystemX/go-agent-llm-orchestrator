package worker

import (
	"context"
	"go-agent-llm-orchestrator/internal/db"
)

// Executor определяет интерфейс для выполнения задач.
// Это может быть как удаленный сервис (Jules), так и локальный агент (Ollama + MCP).
type Executor interface {
	// Execute запускает выполнение задачи и возвращает ID сессии.
	Execute(ctx context.Context, task *db.Task, prompt string, logID int64) (sessionID string, err error)
	
	// GetStatus возвращает текущий статус выполнения сессии.
	GetStatus(ctx context.Context, sessionID string) (status string, err error)
	
	// Cancel прерывает выполнение задачи.
	Cancel(ctx context.Context, sessionID string) error
}
