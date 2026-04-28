package scheduler

import (
	"context"
)

// VerificationResult represents the outcome of a task verification step.
type VerificationResult struct {
	Success bool
	Error   string // Error message to feed back to the agent
	Details string // Additional context for the UI
}

// TaskVerifier defines how to check if a task was successful.
type TaskVerifier interface {
	Verify(ctx context.Context, repoName string, sessionID string) (VerificationResult, error)
}

// GitHubVerifier checks CI status of a PR opened by the agent.
type GitHubVerifier struct {
	// In a real app, this would use a GitHub client
}

func (v *GitHubVerifier) Verify(ctx context.Context, repoName string, sessionID string) (VerificationResult, error) {
	// Mock implementation for now
	return VerificationResult{Success: true}, nil
}
