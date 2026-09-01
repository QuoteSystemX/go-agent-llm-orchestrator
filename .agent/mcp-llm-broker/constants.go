package main

// Local LLM Provider names
const (
	ProviderOllama      = "ollama"
	ProviderJan         = "jan"
	ProviderLMStudio    = "lm-studio"
	ProviderLlamaCpp    = "llamacpp"
	ProviderAntigravity = "antigravity"
)

// Default service URLs and ports
const (
	DefaultOllamaURL   = "http://localhost:11434"
	DefaultJanURL      = "http://localhost:1337"
	DefaultLMStudioURL = "http://localhost:1234"
	// DefaultLlamaCppURL is a fallback only — a standalone llama-server is typically
	// started with a random/user-chosen port, so the real address should be set via
	// RouterRules.LlamaCppBaseURL (router_rules.json "llamacpp_base_url") and is
	// re-read on every call, no broker restart needed after changing the port.
	DefaultLlamaCppURL = "http://localhost:8080"

	OllamaDefaultPortStr = "11434"
)

// llamaCppDefaultSourceRef pins the llama.cpp release tag the provisioner builds
// from source when RouterRules.LlamaCppSourceRef is unset. Bump via
// router_rules.json "llamacpp_source_ref" to build a newer release without a
// broker code change.
const llamaCppDefaultSourceRef = "b10069"

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
	ProviderLlamaCpp:    {InputPricePer1K: 0.0, OutputPricePer1K: 0.0},
}

// Circuit breaker states
const (
	CircuitClosed   = 0 // Normal operation
	CircuitOpen     = 1 // Backend failed — skip instantly
	CircuitHalfOpen = 2 // Testing recovery — allow 1 probe request
)

// Circuit breaker default thresholds (overridable via router_rules.json "circuit_breaker")
const (
	CBDefaultFailureThreshold = 3      // consecutive failures before tripping Open
	CBDefaultRecoveryTimeoutS = 120    // seconds in Open before trying Half-Open (self-hosted = slow HW)
	CBDefaultSoftEMAThreshold = 5000.0 // ms/token — soft-circuit EMA threshold (5s/token)
)

// Sub-agent read-only tool loop defaults (overridable via router_rules.json
// "sub_agent_tools" — see SubAgentToolsConfig). Govern the read_file/grep
// tools available to tool-enabled local-only sub-agent dispatches
// (withToolsEnabled) — see tools_readonly.go and executeOllamaToolLoop.
const (
	ToolLoopDefaultMaxCalls            = 5          // per-dispatch tool-call budget
	ToolLoopDefaultMaxBytesPerCall     = 32 * 1024  // 32KB — single read_file/grep response cap
	ToolLoopDefaultMaxBytesPerDispatch = 250 * 1024 // 250KB — cumulative cap across all calls in one dispatch
	ToolLoopDefaultMaxGrepMatches      = 50
	ToolLoopDefaultMaxIterations       = 6 // > MaxCalls, leaves room for a final synthesis turn
)
