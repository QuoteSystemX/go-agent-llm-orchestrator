package traffic

import (
	"context"
	"testing"
	"time"
)

type mockChecker struct{}

func (m *mockChecker) GetDailyUsage(ctx context.Context) (int, error) { return 0, nil }
func (m *mockChecker) GetDailyLimit(ctx context.Context) (int, error) { return 0, nil }

type mockUsageChecker struct {
	usage int
	limit int
}

func (m *mockUsageChecker) GetDailyUsage(ctx context.Context) (int, error) { return m.usage, nil }
func (m *mockUsageChecker) GetDailyLimit(ctx context.Context) (int, error) { return m.limit, nil }

func TestTrafficManager_Wait(t *testing.T) {
	tm := NewTrafficManager(10, 1, &mockChecker{}) // 10 RPS, burst 1
	ctx := context.Background()

	// First call should be immediate
	start := time.Now()
	err := tm.Wait(ctx, PriorityHigh, 1, "worker")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	// Second call should be throttled (at least 100ms)
	err = tm.Wait(ctx, PriorityLow, 1, "worker")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	elapsed := time.Since(start)

	if elapsed < 90*time.Millisecond {
		t.Errorf("expected throttling, but elapsed only %v", elapsed)
	}
}

func TestTrafficManager_BudgetAware(t *testing.T) {
	ctx := context.Background()
	mock := &mockUsageChecker{
		usage: 95,
		limit: 100,
	}
	tm := NewTrafficManager(10, 10, mock)

	// 95% usage: Service task with importance 8 should pass
	err := tm.Wait(ctx, PriorityHigh, 8, "service")
	if err != nil {
		t.Errorf("expected high-importance service task to pass, got: %v", err)
	}

	// 95% usage: Worker task should fail
	err = tm.Wait(ctx, PriorityHigh, 5, "worker")
	if err == nil {
		t.Error("expected worker task to fail at 95% budget")
	}

	// 100% usage: All should fail
	mock.usage = 100
	err = tm.Wait(ctx, PriorityHigh, 10, "service")
	if err != ErrDailyLimitExceeded {
		t.Errorf("expected ErrDailyLimitExceeded, got: %v", err)
	}
}
