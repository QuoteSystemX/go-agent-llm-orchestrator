package main

// Local LLM Provider names
const (
	ProviderOllama      = "ollama"
	ProviderJan         = "jan"
	ProviderLMStudio    = "lm-studio"
	ProviderAntigravity = "antigravity"
)

// Default service URLs and ports
const (
	DefaultOllamaURL   = "http://localhost:11434"
	DefaultJanURL      = "http://localhost:1337"
	DefaultLMStudioURL = "http://localhost:1234"

	OllamaDefaultPortStr = "11434"
	HeadroomPortStr      = "8787"
)

// Latency balancing constants
const (
	// Maximum EMA ms/token before a backend is excluded from candidates
	EMALatencyThresholdMsPerToken = 10000.0 // 10 seconds per token = effectively dead
	// EMA smoothing factor (alpha)
	EMAAlpha = 0.3
	// Minimum total tokens before EMA is considered reliable
	EMAMinTokensForReliability = 100
)

// Default provider pricing in USD per 1K tokens (input/output)
var DefaultProviderPrices = map[string]ProviderPricing{
	ProviderAntigravity: {InputPricePer1K: 0.00015, OutputPricePer1K: 0.00060},
	ProviderOllama:      {InputPricePer1K: 0.0, OutputPricePer1K: 0.0}, // local = free
	ProviderJan:         {InputPricePer1K: 0.0, OutputPricePer1K: 0.0},
	ProviderLMStudio:    {InputPricePer1K: 0.0, OutputPricePer1K: 0.0},
}

// Circuit breaker states
const (
	CircuitClosed   = 0 // Normal operation
	CircuitOpen     = 1 // Backend failed — skip instantly
	CircuitHalfOpen = 2 // Testing recovery — allow 1 probe request
)

// Circuit breaker default thresholds (overridable via router_rules.json "circuit_breaker")
const (
	CBDefaultFailureThreshold = 3     // consecutive failures before tripping Open
	CBDefaultRecoveryTimeoutS = 120   // seconds in Open before trying Half-Open (self-hosted = slow HW)
	CBDefaultSoftEMAThreshold = 5000.0 // ms/token — soft-circuit EMA threshold (5s/token)
)

