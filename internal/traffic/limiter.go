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
}

// NewTrafficManager creates a new limiter with given requests per second and burst size
func NewTrafficManager(rps float64, burst int, checker UsageChecker) *TrafficManager {
	return &TrafficManager{
		limiter: rate.NewLimiter(rate.Limit(rps), burst),
		checker: checker,
	}
}

// Wait blocks until the rate limiter allows the call based on priority.
func (tm *TrafficManager) Wait(ctx context.Context, p Priority) error {
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

		if limit > 0 && usage >= limit {
			return ErrDailyLimitExceeded
		}
	}

	// 2. Standard RPS limiting
	return tm.limiter.Wait(ctx)
}

// Execute wraps a function call with rate limiting
func (tm *TrafficManager) Execute(ctx context.Context, p Priority, fn func() error) error {
	if err := tm.Wait(ctx, p); err != nil {
		return err
	}
	return fn()
}
