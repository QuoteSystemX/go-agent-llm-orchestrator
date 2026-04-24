package traffic

import (
	"context"
	"errors"
	"sync"

	"golang.org/x/time/rate"
)

type Priority int

const (
	PriorityHigh Priority = 1 // Scheduling
	PriorityLow  Priority = 2 // Monitoring
)

var (
	ErrDailyLimitExceeded = errors.New("daily task limit exceeded")
)

type UsageChecker interface {
	GetDailyUsage(ctx context.Context) (int, error)
	GetDailyLimit(ctx context.Context) (int, error)
}

// TrafficManager handles rate limiting with priority awareness and daily quotas
type TrafficManager struct {
	limiter *rate.Limiter
	checker UsageChecker
	mu      sync.Mutex
	sem     chan struct{} // Semaphore for worker pool
}

// NewTrafficManager creates a new limiter with given requests per second, burst size and worker limit
func NewTrafficManager(rps float64, burst int, workers int, checker UsageChecker) *TrafficManager {
	var sem chan struct{}
	if workers > 0 {
		sem = make(chan struct{}, workers)
	}
	return &TrafficManager{
		limiter: rate.NewLimiter(rate.Limit(rps), burst),
		checker: checker,
		sem:     sem,
	}
}

// Wait blocks until the rate limiter allows the call based on priority.
func (tm *TrafficManager) Wait(ctx context.Context, p Priority, importance int, category string) error {
	// 1. Check daily limit first if it's a High priority (task execution) call
	if p == PriorityHigh && tm.checker != nil {
		usage, err := tm.checker.GetDailyUsage(ctx)
		if err != nil {
			return err
		}
		limit, err := tm.checker.GetDailyLimit(ctx)
		if err != nil {
			return err
		}

		if limit > 0 {
			// Budget-aware prioritization
			pct := float64(usage) / float64(limit)

			if usage >= limit {
				return ErrDailyLimitExceeded
			}

			// Critical budget: > 90%
			if pct > 0.9 {
				// Only Service tasks with importance >= 8 or any task with importance >= 10
				if importance < 10 && (category != "service" || importance < 8) {
					return errors.New("daily budget critical: only high importance service tasks allowed")
				}
			} else if pct > 0.75 {
				// > 75%: Only importance >= 5 or any service task
				if importance < 5 && category != "service" {
					return errors.New("daily budget low: only service or mid-importance tasks allowed")
				}
			}
		}
	}

	// 2. Standard RPS limiting
	return tm.limiter.Wait(ctx)
}

// Execute wraps a function call with rate limiting and worker pool management
func (tm *TrafficManager) Execute(ctx context.Context, p Priority, importance int, category string, fn func() error) error {
	if err := tm.Wait(ctx, p, importance, category); err != nil {
		return err
	}

	if tm.sem != nil {
		select {
		case tm.sem <- struct{}{}:
			defer func() { <-tm.sem }()
		case <-ctx.Done():
			return ctx.Err()
		}
	}

	return fn()
}
