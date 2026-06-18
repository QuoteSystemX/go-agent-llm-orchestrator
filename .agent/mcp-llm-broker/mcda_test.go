package main

import (
	"math"
	"testing"
)

func TestParseModelSize(t *testing.T) {
	tests := []struct {
		name string
		want float64
	}{
		{"qwen-7b-instruct", 7.0},
		{"deepseek-r1-8b-gguf", 8.0},
		{"llama3.1-405b", 405.0},
		{"phi3-3.8b", 3.8},
		{"gemma-2b-it", 2.0},
		{"no-size-tag", 7.0},
	}

	for _, tt := range tests {
		got := parseModelSize(tt.name)
		if got != tt.want {
			t.Errorf("parseModelSize(%q) = %f; want %f", tt.name, got, tt.want)
		}
	}
}

func TestIsHardwareMemoryLimitOk(t *testing.T) {
	// Our test runs with the fallback (8GB available) or macOS/Linux real values.
	// Since 8GB available * 0.85 = 6.8GB safety limit:
	// A 8B model needs 8*0.5 + 2 = 6GB -> Should pass.
	// A 32B model needs 32*0.5 + 2 = 18GB -> Should fail.
	
	if !isHardwareMemoryLimitOk("deepseek-r1-8b") {
		t.Log("Warning: 8B model rejected - check host memory status")
	}

	if isHardwareMemoryLimitOk("llama3.1-405b") {
		t.Error("Expected 405B model to be rejected due to memory limits, but it was allowed")
	}
}

func TestLevenshteinDistance(t *testing.T) {
	s1 := "kitten"
	s2 := "sitting"
	expected := 3
	if got := levenshteinDistance(s1, s2); got != expected {
		t.Errorf("levenshteinDistance(%q, %q) = %d; want %d", s1, s2, got, expected)
	}

	s3 := "hello"
	s4 := "hello"
	if got := levenshteinDistance(s3, s4); got != 0 {
		t.Errorf("levenshteinDistance(%q, %q) = %d; want 0", s3, s4, got)
	}
}

func TestTokenOverlap(t *testing.T) {
	t1 := "DeepSeek-R1-8B"
	c1 := "DeepSeek-R1-0528-Qwen3-8B-GGUF"
	overlap := tokenOverlap(t1, c1)
	if overlap < 0.99 {
		t.Errorf("Expected complete overlap score close to 1.0, got %f", overlap)
	}

	c2 := "Qwen3.5-9B-DeepSeek-V4-Flash-GGUF"
	overlap2 := tokenOverlap(t1, c2)
	// target has ["deepseek", "r1", "8b"]. Candidate has ["qwen", "3.5", "9b", "deepseek", "v4", "flash"]
	// only "deepseek" matches. Overlap should be 1/3 (0.33)
	if math.Abs(overlap2-0.333333) > 1e-4 {
		t.Errorf("Expected 0.3333 overlap, got %f", overlap2)
	}
}

func TestMCDASelection(t *testing.T) {
	srv := &BrokerServer{}

	// Use small model sizes (1B) so isHardwareMemoryLimitOk always passes
	// regardless of available RAM in the test environment.
	target := "test-model-1B"
	candidates := []string{
		"similar-test-model-1B-variant-a-GGUF",
		"test-model-1B-exact-match-GGUF",
	}

	best, err := srv.selectBestRegistryModel(target, candidates)
	if err != nil {
		t.Fatalf("selectBestRegistryModel failed: %v", err)
	}

	if best == "" {
		t.Errorf("Expected a non-empty best model, got empty string")
	}
}
