package main

import (
	"context"
	"encoding/json"
	"net/http"
	"os"
	"path/filepath"
	"testing"
	"time"
)

// Helper to write mock router rules
func writeTestRouterRules(t *testing.T, srv *BrokerServer, rules *RouterRules) {
	rulesDir := filepath.Join(srv.workspaceRoot, ".agent", "config")
	err := os.MkdirAll(rulesDir, 0755)
	if err != nil {
		t.Fatalf("Failed to create rules dir: %v", err)
	}
	rulesPath := filepath.Join(rulesDir, "router_rules.json")
	data, err := json.Marshal(rules)
	if err != nil {
		t.Fatalf("Failed to marshal rules: %v", err)
	}
	err = os.WriteFile(rulesPath, data, 0644)
	if err != nil {
		t.Fatalf("Failed to write rules: %v", err)
	}
}

// 1. TestCircuitBreaker_TripsAfterThreshold: 3 failures -> transition to Open
func TestCircuitBreaker_TripsAfterThreshold(t *testing.T) {
	srv := &BrokerServer{
		workspaceRoot: t.TempDir(),
		healthCache:   make(map[string]BackendHealth),
	}

	// Default threshold = 3
	srv.recordProviderFailure("jan")
	srv.recordProviderFailure("jan")
	h := srv.getBackendHealth("jan")
	if h.CircuitState != CircuitClosed {
		t.Errorf("Expected Closed state, got %d", h.CircuitState)
	}

	srv.recordProviderFailure("jan")
	h = srv.getBackendHealth("jan")
	if h.CircuitState != CircuitOpen {
		t.Errorf("Expected Open state after 3 failures, got %d", h.CircuitState)
	}
}

// 2. TestCircuitBreaker_RecoveryTimeout: Open -> HalfOpen after recovery timeout
func TestCircuitBreaker_RecoveryTimeout(t *testing.T) {
	srv := &BrokerServer{
		workspaceRoot: t.TempDir(),
		healthCache: map[string]BackendHealth{
			"jan": {
				CircuitState:    CircuitOpen,
				LastFailureTime: time.Now().Add(-150 * time.Second), // older than default 120s
			},
		},
	}

	// This should transition state to HalfOpen and return false (not open anymore)
	isOpen := srv.isCircuitOpen("jan")
	if isOpen {
		t.Error("Expected circuit to not be open (should be half-open)")
	}

	h := srv.getBackendHealth("jan")
	if h.CircuitState != CircuitHalfOpen {
		t.Errorf("Expected state to be HalfOpen, got %d", h.CircuitState)
	}
}

// 3. TestCircuitBreaker_HalfOpenSuccess: HalfOpen + success -> Closed
func TestCircuitBreaker_HalfOpenSuccess(t *testing.T) {
	srv := &BrokerServer{
		workspaceRoot: t.TempDir(),
		healthCache: map[string]BackendHealth{
			"jan": {
				CircuitState: CircuitHalfOpen,
			},
		},
	}

	// recordProviderSuccess should transition to CircuitClosed
	srv.recordProviderSuccess("jan")
	h := srv.getBackendHealth("jan")
	if h.CircuitState != CircuitClosed {
		t.Errorf("Expected Closed state after success in HalfOpen, got %d", h.CircuitState)
	}
	if h.ConsecutiveFailures != 0 {
		t.Errorf("Expected consecutive failures to be reset to 0, got %d", h.ConsecutiveFailures)
	}
}

// 4. TestCircuitBreaker_HalfOpenFailure: HalfOpen + error -> Open (reset recovery timer)
func TestCircuitBreaker_HalfOpenFailure(t *testing.T) {
	srv := &BrokerServer{
		workspaceRoot: t.TempDir(),
		healthCache: map[string]BackendHealth{
			"jan": {
				CircuitState: CircuitHalfOpen,
			},
		},
	}

	// recordProviderFailure should transition to CircuitOpen immediately
	srv.recordProviderFailure("jan")
	h := srv.getBackendHealth("jan")
	if h.CircuitState != CircuitOpen {
		t.Errorf("Expected Open state after failure in HalfOpen, got %d", h.CircuitState)
	}
}

// 5. TestCircuitBreaker_SoftEMA: High EMA -> soft open
func TestCircuitBreaker_SoftEMA(t *testing.T) {
	srv := &BrokerServer{
		workspaceRoot: t.TempDir(),
		healthCache: map[string]BackendHealth{
			"jan": {
				CircuitState:  CircuitClosed,
				EMAMsPerToken: 6000.0, // defaults threshold is 5000.0
				TotalTokens:   200,    // >= 100 threshold
			},
		},
	}

	// isCircuitOpen should return true due to soft EMA open logic
	isOpen := srv.isCircuitOpen("jan")
	if !isOpen {
		t.Error("Expected circuit to be open due to high EMA latency")
	}
}

// 6. TestCircuitBreaker_SuccessResetsCounter: Success in between errors resets count
func TestCircuitBreaker_SuccessResetsCounter(t *testing.T) {
	srv := &BrokerServer{
		workspaceRoot: t.TempDir(),
		healthCache:   make(map[string]BackendHealth),
	}

	srv.recordProviderFailure("jan")
	srv.recordProviderFailure("jan")
	srv.recordProviderSuccess("jan")
	srv.recordProviderFailure("jan")

	h := srv.getBackendHealth("jan")
	if h.CircuitState != CircuitClosed {
		t.Errorf("Expected CircuitClosed, got %d", h.CircuitState)
	}
	if h.ConsecutiveFailures != 1 {
		t.Errorf("Expected 1 failure, got %d", h.ConsecutiveFailures)
	}
}

// 7. TestCircuitBreaker_SkipsCandidateInRouting: Open provider is excluded from candidate list
func TestCircuitBreaker_SkipsCandidateInRouting(t *testing.T) {
	srv := &BrokerServer{
		workspaceRoot: t.TempDir(),
		healthCache: map[string]BackendHealth{
			"jan":    {CircuitState: CircuitOpen, LastFailureTime: time.Now()}, // jan is open
			"ollama": {CircuitState: CircuitClosed},                            // ollama is closed
		},
	}
	rules := &RouterRules{
		Models: map[string]ModelTiers{
			"ollama": {
				"L2": "ollama-model",
			},
			"jan": {
				"L2": "jan-model",
			},
		},
		ModelRankings: map[string]json.RawMessage{
			"jan-model":    []byte(`{"rank_score": 90}`),
			"ollama-model": []byte(`{"rank_score": 80}`),
		},
	}
	writeTestRouterRules(t, srv, rules)

	// Since jan is open, even though jan-model has higher rank score (90 > 80), jan candidate must be skipped.
	// Only ollama-model candidate should be returned.
	pulledModels := map[string]string{
		"jan-model":    "jan",
		"ollama-model": "ollama",
	}

	candidates := srv.getLocalCandidates("L2", rules, pulledModels)
	if len(candidates) != 1 {
		t.Fatalf("Expected exactly 1 candidate, got %d", len(candidates))
	}
	if candidates[0].Model != "ollama-model" || candidates[0].Provider != "ollama" {
		t.Errorf("Expected ollama-model/ollama candidate, got %s/%s", candidates[0].Model, candidates[0].Provider)
	}
}

// 8. TestGracefulShutdown_DrainTimeout: HTTP server shutdown within 30s
func TestGracefulShutdown_DrainTimeout(t *testing.T) {
	srv := &BrokerServer{
		workspaceRoot: t.TempDir(),
		healthCache:   make(map[string]BackendHealth),
	}

	httpSrv := srv.createHTTPServer(0) // 0 lets the OS choose a random free port

	errCh := make(chan error, 1)
	go func() {
		errCh <- httpSrv.ListenAndServe()
	}()

	// Wait a moment for server to bind
	time.Sleep(100 * time.Millisecond)

	// Shutdown the server gracefully with a small timeout
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()

	err := httpSrv.Shutdown(ctx)
	if err != nil {
		t.Fatalf("Failed to shutdown gracefully: %v", err)
	}

	select {
	case listenErr := <-errCh:
		if listenErr != http.ErrServerClosed {
			t.Errorf("Expected ErrServerClosed, got %v", listenErr)
		}
	case <-time.After(3 * time.Second):
		t.Error("Server did not stop listening within 3 seconds")
	}
}
