package monitor

import (
	"context"
	"time"
)

type TraceType string

const (
	TraceThought TraceType = "thought"
	TraceRAG     TraceType = "rag"
	TraceTool    TraceType = "tool"
	TraceOutput  TraceType = "output"
)

type AgentTraceEvent struct {
	TaskID    string    `json:"task_id"`
	StepID    string    `json:"step_id"`
	Type      TraceType `json:"type"`
	Content   string    `json:"content"`
	Metadata  any       `json:"metadata,omitempty"`
	Timestamp time.Time `json:"ts"`
}

type Tracer interface {
	BroadcastTrace(event AgentTraceEvent)
}

type contextKey string

const taskIDKey contextKey = "task_id"

// WithTaskID injects TaskID into context
func WithTaskID(ctx context.Context, taskID string) context.Context {
	return context.WithValue(ctx, taskIDKey, taskID)
}

// GetTaskID retrieves TaskID from context
func GetTaskID(ctx context.Context) string {
	if val, ok := ctx.Value(taskIDKey).(string); ok {
		return val
	}
	return ""
}
