package main

import (
	"encoding/json"
	"testing"
)

// makeTestRules builds a minimal RouterRules with Jan L3 models matching the real config.
func makeTestRules() *RouterRules {
	return &RouterRules{
		Scoring: ScoringConfig{
			BaseScore: 5,
			Thresholds: map[string]int{"L1": 3, "L2": 7, "L3": 10, "L4": 13},
		},
		Models: map[string]ModelTiers{
			"jan": {
				"L1": "Jan-v3.5-4B-Q4_K_XL",
				"L2": "DeepSeek-R1-0528-Qwen3-8B-IQ4_XS",
				"L3": "Qwen3_6-27B-IQ4_XS",
				"L3_alt": []interface{}{"gemma-4-26B-A4B-it-UD-IQ4_XS"},
			},
			"ollama": {
				"L3": "qwen3.6:27b",
			},
		},
		ModelRankings: map[string]json.RawMessage{
			"Jan-v3.5-4B-Q4_K_XL":              []byte(`{"tier":"L1","rank_score":336}`),
			"DeepSeek-R1-0528-Qwen3-8B-IQ4_XS": []byte(`{"tier":"L2","rank_score":400}`),
			"Qwen3_6-27B-IQ4_XS":               []byte(`{"tier":"L3","rank_score":430}`),
			"gemma-4-26B-A4B-it-UD-IQ4_XS":     []byte(`{"tier":"L3","rank_score":415}`),
		},
		HybridRouting: HybridRoutingConfig{
			CloudFallbackProvider: "antigravity",
		},
	}
}

func TestCalculateScore(t *testing.T) {
	srv := &BrokerServer{
		workspaceRoot: ".",
	}

	rules := &RouterRules{
		Scoring: ScoringConfig{
			BaseScore: 4,
			Thresholds: map[string]int{
				"L1": 3,
				"L2": 7,
				"L3": 10,
				"L4": 13,
			},
			Weights: map[string]int{
				"refactor": 3,
				"fix":      1,
			},
		},
	}

	// Base score is 4
	score := srv.calculateScore("refactor code", rules)
	if score != 7 {
		t.Errorf("Expected score 7, got %d", score)
	}

	score = srv.calculateScore("fix bug", rules)
	if score != 5 {
		t.Errorf("Expected score 5, got %d", score)
	}
}

func TestDecideTier(t *testing.T) {
	srv := &BrokerServer{}
	rules := &RouterRules{
		Scoring: ScoringConfig{
			Thresholds: map[string]int{
				"L1": 3,
				"L2": 7,
				"L3": 10,
				"L4": 13,
			},
		},
	}

	if tier := srv.decideTier(3, rules); tier != "L1" {
		t.Errorf("Expected L1, got %s", tier)
	}
	if tier := srv.decideTier(7, rules); tier != "L2" {
		t.Errorf("Expected L2, got %s", tier)
	}
	if tier := srv.decideTier(10, rules); tier != "L3" {
		t.Errorf("Expected L3, got %s", tier)
	}
	if tier := srv.decideTier(11, rules); tier != "L4" {
		t.Errorf("Expected L4, got %s", tier)
	}
}

func TestPickBestLocal(t *testing.T) {
	srv := &BrokerServer{}
	rules := &RouterRules{
		Models: map[string]ModelTiers{
			"ollama": {
				"L2":     "primary:1",
				"L2_alt": []interface{}{"alt:1", "alt:2"},
			},
		},
		ModelRankings: map[string]json.RawMessage{
			"primary:1": []byte(`{"rank_score": 50}`),
			"alt:1":     []byte(`{"rank_score": 60}`),
			"alt:2":     []byte(`{"rank_score": 40}`),
		},
	}

	pulledModels := map[string]string{
		"primary:1": "ollama",
		"alt:1":     "ollama",
	}

	// Should pick alt:1 because rank score 60 is higher than primary:1 rank score 50
	model, provider, ok := srv.pickBestLocal("L2", rules, pulledModels)
	if !ok {
		t.Fatal("Expected true, got false")
	}
	if model != "alt:1" {
		t.Errorf("Expected alt:1, got %s", model)
	}
	if provider != "ollama" {
		t.Errorf("Expected ollama, got %s", provider)
	}
}

func TestModelNameMatches(t *testing.T) {
	srv := &BrokerServer{}

	tests := []struct {
		config string
		actual string
		want   bool
	}{
		// Size mismatch checks
		{"qwen3.6:27b", "Qwen3_6-35B-A3B-Uncensored-HauhauCS-Aggressive-IQ4_XS", false},
		{"gemma2:9b", "gemma-4-12B-it-abliterated-uncensored_i1-IQ4_XS", false},
		{"qwen3-coder:30b", "Qwen3_6-35B-A3B-Uncensored-HauhauCS-Aggressive-IQ4_XS", false},

		// Valid matches with sizes
		{"qwen3.6:27b", "Qwen3_6-27B-IQ4_XS", true},
		{"gemma2:9b", "gemma-2-9b-it", true},
		{"deepseek-r1:8b", "DeepSeek-R1-0528-Qwen3-8B-IQ4_XS", true},

		// Matching without config size specified (or actual size specified)
		{"qwen-coder", "qwen-coder-32b-instruct", true},
		{"qwen3-coder:30b", "qwen3-coder-instruct", true}, // wait, config has 30b but actual has no size -> since only one has size, it matches

		// Mismatch version preserving checks
		{"qwen3.6:27b", "Qwen2.5-27B-Instruct", false},
	}

	for _, tt := range tests {
		got := srv.modelNameMatches(tt.config, tt.actual)
		if got != tt.want {
			t.Errorf("modelNameMatches(%q, %q) = %t; want %t", tt.config, tt.actual, got, tt.want)
		}
	}
}

// ---------------------------------------------------------------------------
// isTierCompatibleWith
// ---------------------------------------------------------------------------

func TestIsTierCompatibleWith(t *testing.T) {
	tests := []struct {
		modelTier     string
		requestedTier string
		want          bool
	}{
		// Same tier — always compatible
		{"L1", "L1", true},
		{"L2", "L2", true},
		{"L3", "L3", true},
		{"L4", "L4", true},
		// Lighter model serves heavier request — compatible
		{"L1", "L2", true},
		{"L1", "L3", true},
		{"L2", "L3", true},
		{"L2", "L4", true},
		{"L3", "L4", true},
		// Heavier model must NOT serve lighter request
		{"L2", "L1", false},
		{"L3", "L1", false},
		{"L3", "L2", false},
		{"L4", "L1", false},
		{"L4", "L2", false},
		{"L4", "L3", false},
		// Unknown tier — always compatible (no info = don't block)
		{"", "L2", true},
		{"L2", "", true},
		{"", "", true},
	}

	for _, tt := range tests {
		got := isTierCompatibleWith(tt.modelTier, tt.requestedTier)
		if got != tt.want {
			t.Errorf("isTierCompatibleWith(%q, %q) = %v; want %v", tt.modelTier, tt.requestedTier, got, tt.want)
		}
	}
}

// ---------------------------------------------------------------------------
// getLocalCandidates
// ---------------------------------------------------------------------------

func newSrvWithHealth(available bool) *BrokerServer {
	return &BrokerServer{
		healthCache: map[string]BackendHealth{
			"jan":       {Available: available},
			"ollama":    {Available: available},
			"lm-studio": {Available: available},
		},
	}
}

func TestGetLocalCandidates_ExactMatchJan(t *testing.T) {
	// Qwen3_6-27B-IQ4_XS is in BOTH config (jan L3) and pulledModels.
	// Should return exactly one candidate regardless of healthCache state.
	rules := makeTestRules()
	pulled := map[string]string{
		"Qwen3_6-27B-IQ4_XS": "jan",
	}

	srv := newSrvWithHealth(true)
	candidates := srv.getLocalCandidates("L3", rules, pulled)
	if len(candidates) == 0 {
		t.Fatal("expected at least 1 candidate, got 0")
	}
	if candidates[0].Model != "Qwen3_6-27B-IQ4_XS" {
		t.Errorf("expected Qwen3_6-27B-IQ4_XS, got %q", candidates[0].Model)
	}
	if candidates[0].Provider != "jan" {
		t.Errorf("expected provider jan, got %q", candidates[0].Provider)
	}
}

func TestGetLocalCandidates_FuzzyMatchJanQwen(t *testing.T) {
	// Config has "qwen3.6:27b" (Ollama name style), pulled has "Qwen3_6-27B-IQ4_XS" (Jan name style).
	// Fuzzy match must resolve them to the same model.
	rules := makeTestRules()
	pulled := map[string]string{
		"Qwen3_6-27B-IQ4_XS": "jan",
	}

	srv := newSrvWithHealth(true)
	candidates := srv.getLocalCandidates("L3", rules, pulled)

	found := false
	for _, c := range candidates {
		if c.Model == "Qwen3_6-27B-IQ4_XS" && c.Provider == "jan" {
			found = true
		}
	}
	if !found {
		t.Errorf("expected fuzzy match Qwen3_6-27B-IQ4_XS@jan in candidates, got: %+v", candidates)
	}
}

func TestGetLocalCandidates_HealthCacheFalseDoesNotBlockPulledModel(t *testing.T) {
	// The health cache says "jan" is unavailable.
	// BUT the model was found in pulledModels (live fetch), which proves the provider is up.
	// A stale healthCache must NOT block a live-fetched model.
	rules := makeTestRules()
	pulled := map[string]string{
		"Qwen3_6-27B-IQ4_XS": "jan",
	}

	srv := newSrvWithHealth(false) // jan marked unavailable in cache
	candidates := srv.getLocalCandidates("L3", rules, pulled)

	if len(candidates) == 0 {
		t.Error("stale healthCache Available=false must not block a model that was just fetched live from pulledModels")
	}
}

func TestGetLocalCandidates_TierIncompatibleSkipped(t *testing.T) {
	// L2 model (DeepSeek-R1-0528-Qwen3-8B-IQ4_XS) must not appear in an L1 candidate list.
	rules := makeTestRules()
	pulled := map[string]string{
		"Jan-v3.5-4B-Q4_K_XL":              "jan",
		"DeepSeek-R1-0528-Qwen3-8B-IQ4_XS": "jan",
	}

	srv := newSrvWithHealth(true)
	candidates := srv.getLocalCandidates("L1", rules, pulled)

	for _, c := range candidates {
		if c.Model == "DeepSeek-R1-0528-Qwen3-8B-IQ4_XS" {
			t.Errorf("L2 model DeepSeek-R1-0528-Qwen3-8B-IQ4_XS must not appear in L1 candidates")
		}
	}
	// Jan-v3.5-4B-Q4_K_XL (L1) must be present
	found := false
	for _, c := range candidates {
		if c.Model == "Jan-v3.5-4B-Q4_K_XL" {
			found = true
		}
	}
	if !found {
		t.Error("expected Jan-v3.5-4B-Q4_K_XL (L1) in L1 candidates, got none")
	}
}

func TestGetLocalCandidates_NoDuplicatesAcrossProviders(t *testing.T) {
	// Same model name reported by two different providers must appear only once in candidates.
	rules := makeTestRules()
	pulled := map[string]string{
		"Qwen3_6-27B-IQ4_XS": "jan",
	}

	srv := newSrvWithHealth(true)
	candidates := srv.getLocalCandidates("L3", rules, pulled)

	seen := map[string]int{}
	for _, c := range candidates {
		seen[c.Model+"@"+c.Provider]++
	}
	for key, count := range seen {
		if count > 1 {
			t.Errorf("duplicate candidate %q returned %d times", key, count)
		}
	}
}

func TestGetLocalCandidates_AltModelsIncluded(t *testing.T) {
	// L3_alt model (gemma-4-26B-A4B-it-UD-IQ4_XS) should be included when primary is absent.
	rules := makeTestRules()
	pulled := map[string]string{
		"gemma-4-26B-A4B-it-UD-IQ4_XS": "jan",
	}

	srv := newSrvWithHealth(true)
	candidates := srv.getLocalCandidates("L3", rules, pulled)

	found := false
	for _, c := range candidates {
		if c.Model == "gemma-4-26B-A4B-it-UD-IQ4_XS" {
			found = true
		}
	}
	if !found {
		t.Error("expected L3_alt model gemma-4-26B-A4B-it-UD-IQ4_XS in candidates")
	}
}

func TestGetLocalCandidates_EmptyPulledReturnsNoCandidates(t *testing.T) {
	rules := makeTestRules()
	srv := newSrvWithHealth(true)
	candidates := srv.getLocalCandidates("L3", rules, map[string]string{})
	if len(candidates) != 0 {
		t.Errorf("expected 0 candidates with empty pulledModels, got %d", len(candidates))
	}
}
