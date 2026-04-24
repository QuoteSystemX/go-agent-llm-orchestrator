package traffic

import (
	"context"
	"testing"
	"time"
)

type mockChecker struct{}

func (m *mockChecker) GetDailyUsage(ctx context.Context) (int, error) { return 0, nil }
func (m *mockChecker) GetDailyLimit(ctx context.Context) (int, error) { return 0, nil }

func TestTrafficManager_Wait(t *testing.T) {
	tm := NewTrafficManager(10, 1, &mockChecker{}) // 10 RPS, burst 1
	ctx := context.Background()

	// First call should be immediate
	start := time.Now()
	err := tm.Wait(ctx, PriorityHigh)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	// Second call should be throttled (at least 100ms)
	err = tm.Wait(ctx, PriorityLow)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	elapsed := time.Since(start)

	if elapsed < 90*time.Millisecond {
		t.Errorf("expected throttling, but elapsed only %v", elapsed)
	}
}
