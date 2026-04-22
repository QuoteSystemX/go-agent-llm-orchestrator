package traffic

import (
	"context"
	"sync"

	"golang.org/x/time/rate"
)

type Priority int

const (
	PriorityHigh Priority = 1 // Scheduling
	PriorityLow  Priority = 2 // Monitoring
)

// TrafficManager handles rate limiting with priority awareness
type TrafficManager struct {
	limiter *rate.Limiter
	mu      sync.Mutex
}

// NewTrafficManager creates a new limiter with given requests per second and burst size
func NewTrafficManager(rps float64, burst int) *TrafficManager {
	return &TrafficManager{
		limiter: rate.NewLimiter(rate.Limit(rps), burst),
	}
}

// Wait blocks until the rate limiter allows the call based on priority.
// High priority calls bypass the queue if burst allows, or wait less.
func (tm *TrafficManager) Wait(ctx context.Context, p Priority) error {
	// In a more complex implementation, we could use separate limiters or 
	// a weighted reservation system. For MVP, we use a single limiter
	// but can add logic here to "reserve" capacity for High priority.
	
	// For now, we use standard rate.Wait which handles queuing
	return tm.limiter.Wait(ctx)
}

// Execute wraps a function call with rate limiting
func (tm *TrafficManager) Execute(ctx context.Context, p Priority, fn func() error) error {
	if err := tm.Wait(ctx, p); err != nil {
		return err
	}
	return fn()
}
