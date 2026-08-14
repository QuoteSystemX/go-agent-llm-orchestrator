package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
)

type RouterRules struct {
	Scoring          ScoringConfig                    `json:"scoring"`
	Models           map[string]ModelTiers            `json:"models"`
	ModelRankings    map[string]json.RawMessage       `json:"model_rankings"`
	HybridRouting    HybridRoutingConfig              `json:"hybrid_routing"`
	HeadroomProxy    HeadroomProxyConfig              `json:"headroom_proxy"`
	Concurrency      map[string]int                   `json:"concurrency,omitempty"`
	SemanticCache    SemanticCacheConfig              `json:"semantic_cache,omitempty"`
	ProviderSettings map[string]ProviderContextConfig `json:"provider_settings,omitempty"`
	AgentTiers       map[string]string                `json:"agent_tiers,omitempty"`
	DomainTiers      map[string]string                `json:"domain_tiers,omitempty"`
	CircuitBreaker   *CircuitBreakerConfig            `json:"circuit_breaker,omitempty"`
	Timeouts         TimeoutsConfig                   `json:"timeouts,omitempty"`
	// LlamaCppBaseURL is the base URL of a standalone llama-server instance.
	// Unlike Ollama/Jan/LM Studio, its port is not a fixed default — a standalone
	// llama-server is commonly started on a random/user-chosen port — so it must be
	// configured here rather than guessed. Re-read on every loadRules() call, so
	// updating this value takes effect immediately without restarting the broker.
	// The broker's own provisioner (llamacpp_provisioner.go) writes this field back
	// automatically once it launches its own llama-server instance.
	LlamaCppBaseURL string `json:"llamacpp_base_url,omitempty"`
	// LlamaCppSourceRef pins the llama.cpp git tag/ref the provisioner builds from
	// source. Defaults to llamaCppDefaultSourceRef (constants.go) when empty — bump
	// this to build a newer llama.cpp without changing broker code.
	LlamaCppSourceRef string `json:"llamacpp_source_ref,omitempty"`
	// SubAgentTools tunes the sandboxed read_file/grep tools available to
	// tool-enabled local-only sub-agent dispatches (see withToolsEnabled in
	// executor.go). Zero-value fields fall back to the ToolLoopDefault*
	// constants in constants.go.
	SubAgentTools SubAgentToolsConfig `json:"sub_agent_tools,omitempty"`
}

// SubAgentToolsConfig holds the per-dispatch budget for the read_file/grep
// tools given to call_agent-dispatched sub-agent personas. All fields are
// optional — zero values fall back to the ToolLoopDefault* constants.
type SubAgentToolsConfig struct {
	MaxToolCalls        int `json:"max_tool_calls"`         // default: ToolLoopDefaultMaxCalls
	MaxBytesPerCall     int `json:"max_bytes_per_call"`     // default: ToolLoopDefaultMaxBytesPerCall
	MaxBytesPerDispatch int `json:"max_bytes_per_dispatch"` // default: ToolLoopDefaultMaxBytesPerDispatch
	MaxGrepMatches      int `json:"max_grep_matches"`       // default: ToolLoopDefaultMaxGrepMatches
	MaxIterations       int `json:"max_iterations"`         // default: ToolLoopDefaultMaxIterations
}

// resolved returns a copy with every zero field filled from the
// ToolLoopDefault* constants.
func (c SubAgentToolsConfig) resolved() SubAgentToolsConfig {
	if c.MaxToolCalls <= 0 {
		c.MaxToolCalls = ToolLoopDefaultMaxCalls
	}
	if c.MaxBytesPerCall <= 0 {
		c.MaxBytesPerCall = ToolLoopDefaultMaxBytesPerCall
	}
	if c.MaxBytesPerDispatch <= 0 {
		c.MaxBytesPerDispatch = ToolLoopDefaultMaxBytesPerDispatch
	}
	if c.MaxGrepMatches <= 0 {
		c.MaxGrepMatches = ToolLoopDefaultMaxGrepMatches
	}
	if c.MaxIterations <= 0 {
		c.MaxIterations = ToolLoopDefaultMaxIterations
	}
	return c
}

type TimeoutsConfig struct {
	GenerationS    int `json:"generation_s"`
	HealthMs       int `json:"health_ms"`
	SemanticCacheS int `json:"semantic_cache_s"`
}

// CircuitBreakerConfig holds per-workspace circuit breaker tuning knobs.
// All fields are optional — zero values fall back to CBDefault* constants.
type CircuitBreakerConfig struct {
	FailureThreshold int     `json:"failure_threshold"`  // default: 3
	RecoveryTimeoutS int     `json:"recovery_timeout_s"` // default: 120 (for self-hosted / slow HW)
	SoftEMAThreshold float64 `json:"soft_ema_threshold"` // default: 5000.0 ms/token
}

// ProviderContextConfig holds per-provider LLM context window and prefill constraints.
// Stored in router_rules.json under "provider_settings.<provider>".
type ProviderContextConfig struct {
	NCtx        int            `json:"n_ctx"`
	CharsPerTok int            `json:"chars_per_token"`
	PrefillCaps map[string]int `json:"prefill_caps"`
}

// GetProviderCtx returns context window size, chars-per-token estimate, and per-tier
// prefill character caps for the given provider. Falls back to safe defaults when the
// provider is not present in provider_settings.
func (r *RouterRules) GetProviderCtx(provider string) (nCtx, charsPerTok int, prefillCaps map[string]int) {
	const defaultCtx = 8192
	const defaultCharsPerTok = 4
	defaultCaps := map[string]int{"L1": 4000, "L2": 12000, "L3": 24000, "L4": 28000}

	if r == nil || r.ProviderSettings == nil {
		return defaultCtx, defaultCharsPerTok, defaultCaps
	}
	ps, ok := r.ProviderSettings[provider]
	if !ok {
		return defaultCtx, defaultCharsPerTok, defaultCaps
	}
	nCtx = ps.NCtx
	if nCtx <= 0 {
		nCtx = defaultCtx
	}
	charsPerTok = ps.CharsPerTok
	if charsPerTok <= 0 {
		charsPerTok = defaultCharsPerTok
	}
	prefillCaps = ps.PrefillCaps
	if len(prefillCaps) == 0 {
		prefillCaps = defaultCaps
	}
	return
}

type SemanticCacheConfig struct {
	Enabled   bool    `json:"enabled"`
	Threshold float64 `json:"threshold"`
}

type HeadroomProxyConfig struct {
	Enabled              bool   `json:"enabled"`
	Port                 int    `json:"port"`
	UpstreamOllama       string `json:"upstream_ollama"`
	ProxyURL             string `json:"proxy_url"`
	HealthcheckPath      string `json:"healthcheck_path"`
	HealthcheckTimeoutMs int    `json:"healthcheck_timeout_ms"`
	FallbackDirect       bool   `json:"fallback_direct"`
}

type ScoringConfig struct {
	BaseScore      int                  `json:"base_score"`
	FailureContext FailureContextConfig `json:"failure_context"`
	Budget         BudgetConfig         `json:"budget"`
	Thresholds     map[string]int       `json:"thresholds"`
	Weights        map[string]int       `json:"weights"`
}

type FailureContextConfig struct {
	Keywords []string `json:"keywords"`
	MaxBonus int      `json:"max_bonus"`
}

type BudgetConfig struct {
	ThresholdRatio float64 `json:"threshold_ratio"`
	Penalty        int     `json:"penalty"`
}

type ModelTiers map[string]interface{}

type ModelRank struct {
	Tier         string          `json:"tier"`
	QualityScore int             `json:"quality_score"`
	RankScore    float64         `json:"rank_score"`
	Benchmark    BenchmarkConfig `json:"benchmark"`
}

type BenchmarkConfig struct {
	AvgTime float64 `json:"avg_time"`
	AvgTps  float64 `json:"avg_tps"`
	Success float64 `json:"success"`
}

type HybridRoutingConfig struct {
	Enabled               bool     `json:"enabled"`
	PrimaryProvider       string   `json:"primary_provider"`
	CloudFallbackProvider string   `json:"cloud_fallback_provider"`
	OllamaBaseURL         string   `json:"ollama_base_url"`
	OllamaHealthTimeoutMs int      `json:"ollama_health_timeout_ms"`
	CloudOnTiers          []string `json:"cloud_on_tiers"`
}

type RoutingDecision struct {
	ModelID   string   `json:"model_id"`
	Tier      string   `json:"tier"`
	Provider  string   `json:"provider"`
	Score     int      `json:"score"`
	Warning   string   `json:"warning,omitempty"`
	PullHints []string `json:"pull_hints,omitempty"`
}

func (b *BrokerServer) loadRules() (*RouterRules, error) {
	path := filepath.Join(b.workspaceRoot, ".agent", "config", "router_rules.json")
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("failed to read router rules: %w", err)
	}

	var rules RouterRules
	if err := json.Unmarshal(data, &rules); err != nil {
		return nil, fmt.Errorf("failed to unmarshal router rules: %w", err)
	}

	return &rules, nil
}

// makeRoutingDecision calculates the routing decision for a prompt.
// tierHint: if non-empty ("L1"–"L4"), skips complexity scoring and routes directly to that tier.
func (b *BrokerServer) makeRoutingDecision(taskDesc string, pulledModels map[string]string, tierHint string) (*RoutingDecision, error) {
	rules, err := b.loadRules()
	if err != nil {
		return nil, err
	}

	var score int
	var tier string
	if tierHint != "" {
		// Direct tier override — skip complexity scoring
		tier = tierHint
		score = 0
		fmt.Fprintf(os.Stderr, "[DEBUG] router.makeRoutingDecision: tier pinned to %s (no scoring)\n", tier)
	} else {
		// 1. Calculate Score
		score = b.calculateScore(taskDesc, rules)
		// 2. Decide Tier
		tier = b.decideTier(score, rules)
		fmt.Fprintf(os.Stderr, "[DEBUG] router.makeRoutingDecision: taskDesc=%q score=%d tier=%s\n", taskDesc[:min(len(taskDesc), 80)], score, tier)
	}

	// 3. Resolve Provider
	cloudProvider := rules.HybridRouting.CloudFallbackProvider
	cloudOnlyTiers := rules.HybridRouting.CloudOnTiers

	var targetProvider string
	var modelID string
	var warning string
	var pullHints []string

	isCloudOnly := false
	for _, t := range cloudOnlyTiers {
		if t == tier {
			isCloudOnly = true
			break
		}
	}

	if isCloudOnly {
		targetProvider = cloudProvider
		modelID = b.pickBestCloud(tier, rules)
	} else {
		// Try to pick best local pulled model across all running local backends
		bestModel, provider, available := b.pickBestLocal(tier, rules, pulledModels)
		if available {
			modelID = bestModel
			targetProvider = provider
		} else {
			// No local models pulled -> Fallback to cloud
			targetProvider = cloudProvider
			modelID = b.pickBestCloud(tier, rules)

			// Trigger background pull for best matching local candidate that fits host RAM limits
			env := b.detectEnv()
			candidates := b.getConfiguredLocalModels(tier, rules)
			bestCandidate := ""
			for _, c := range candidates {
				if isHardwareMemoryLimitOk(c) {
					bestCandidate = c
					break
				}
			}
			if bestCandidate != "" {
				b.triggerBackgroundPull(bestCandidate, rules, env)
			}

			// Add pull hints
			ollamaMap := rules.Models[ProviderOllama]
			primary := b.getStringOrFirst(ollamaMap[tier])
			alts := b.getStringSlice(ollamaMap[tier+"_alt"])
			allCandidates := append([]string{primary}, alts...)
			for _, m := range allCandidates {
				if m != "" {
					pullHints = append(pullHints, fmt.Sprintf("ollama pull %s", m))
				}
			}

			warning = fmt.Sprintf("No local models pulled for tier %s on any active backend. Request fallback to %s.", tier, cloudProvider)
		}
	}

	return &RoutingDecision{
		ModelID:   modelID,
		Tier:      tier,
		Provider:  targetProvider,
		Score:     score,
		Warning:   warning,
		PullHints: pullHints,
	}, nil
}

func tokenize(text string) map[string]bool {
	tokens := make(map[string]bool)
	var current strings.Builder
	for _, r := range text {
		if (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9') || (r >= 'A' && r <= 'Z') ||
			r == '_' || r == '-' || (r >= 0x0400 && r <= 0x04FF) {
			current.WriteString(strings.ToLower(string(r)))
		} else {
			if current.Len() > 0 {
				tokens[current.String()] = true
				current.Reset()
			}
		}
	}
	if current.Len() > 0 {
		tokens[current.String()] = true
	}
	return tokens
}

func (b *BrokerServer) calculateScore(taskDesc string, rules *RouterRules) int {
	baseScore := rules.Scoring.BaseScore
	if baseScore == 0 {
		baseScore = 5
	}
	score := baseScore

	// Tokenize task description into clean words to prevent false substring matches (e.g. 'lint' in 'splinter')
	tokens := tokenize(taskDesc)

	// 1. Keyword weights
	for kw, weight := range rules.Scoring.Weights {
		matched := false
		kwLower := strings.ToLower(kw)

		// If keyword is a phrase (contains space), use substring match
		if strings.Contains(kwLower, " ") {
			if strings.Contains(strings.ToLower(taskDesc), kwLower) {
				matched = true
			}
		} else {
			// Otherwise match against individual tokens
			for t := range tokens {
				tLower := strings.ToLower(t)
				// 1. Exact or prefix match (stemming)
				if tLower == kwLower || (len(kwLower) >= 3 && strings.HasPrefix(tLower, kwLower)) {
					matched = true
					break
				}
				// 2. Fuzzy match (typos)
				tRunes := []rune(tLower)
				kwRunes := []rune(kwLower)
				compareRunes := tRunes
				if len(tRunes) > len(kwRunes) {
					compareRunes = tRunes[:len(kwRunes)]
				}
				dist := levenshteinDistance(string(compareRunes), kwLower)
				maxAllowedTypos := 1
				if len(kwRunes) >= 6 {
					maxAllowedTypos = 2
				}
				// Only match if keyword length is >= 3 and edit distance is <= allowed typos
				if len(kwRunes) >= 3 && dist <= maxAllowedTypos {
					matched = true
					break
				}
			}
		}

		if matched {
			score += weight
		}
	}

	// 2. Failure context bonus
	score += b.getFailureScore(taskDesc, rules)

	// 3. Budget penalty
	score += b.getBudgetPenalty(rules)

	if score < 1 {
		return 1
	}
	if score > 18 {
		return 18
	}
	return score
}

func (b *BrokerServer) decideTier(score int, rules *RouterRules) string {
	thresholds := rules.Scoring.Thresholds
	if score <= thresholds["L1"] {
		return "L1"
	}
	if score <= thresholds["L2"] {
		return "L2"
	}
	if score <= thresholds["L3"] {
		return "L3"
	}
	return "L4"
}

func (b *BrokerServer) getFailureScore(taskDesc string, rules *RouterRules) int {
	lessonsPath := filepath.Join(b.workspaceRoot, ".agent", "rules", "LESSONS_LEARNED.md")
	data, err := os.ReadFile(lessonsPath)
	if err != nil {
		return 0
	}

	content := strings.ToLower(string(data))
	re := regexp.MustCompile(`\b\w{4,}\b`)
	words := re.FindAllString(strings.ToLower(taskDesc), -1)

	failureKeywords := rules.Scoring.FailureContext.Keywords
	if len(failureKeywords) == 0 {
		failureKeywords = []string{"fail", "error", "retry", "broken", "bug", "hallucination"}
	}

	maxBonus := rules.Scoring.FailureContext.MaxBonus
	if maxBonus == 0 {
		maxBonus = 3
	}

	failureCount := 0
	for _, w := range words {
		if idx := strings.Index(content, w); idx != -1 {
			start := idx - 100
			if start < 0 {
				start = 0
			}
			end := idx + 200
			if end > len(content) {
				end = len(content)
			}
			snippet := content[start:end]

			for _, fk := range failureKeywords {
				if strings.Contains(snippet, fk) {
					failureCount++
					break
				}
			}
		}
	}

	if failureCount > maxBonus {
		return maxBonus
	}
	return failureCount
}

func (b *BrokerServer) getBudgetPenalty(rules *RouterRules) int {
	telemetryPath := filepath.Join(b.workspaceRoot, ".agent", "bus", "telemetry.json")
	watchdogPath := filepath.Join(b.workspaceRoot, ".agent", "config", "watchdog_rules.json")

	telemetryData, err := os.ReadFile(telemetryPath)
	if err != nil {
		return 0
	}
	watchdogData, err := os.ReadFile(watchdogPath)
	if err != nil {
		return 0
	}

	var telemetry map[string]interface{}
	var watchdog map[string]interface{}

	_ = json.Unmarshal(telemetryData, &telemetry)
	_ = json.Unmarshal(watchdogData, &watchdog)

	cost, _ := telemetry["total_cost_usd"].(float64)

	var limit float64 = 2.0
	if limits, ok := watchdog["limits"].(map[string]interface{}); ok {
		if l, ok := limits["cost_limit_per_task_usd"].(float64); ok {
			limit = l
		}
	}

	thresholdRatio := rules.Scoring.Budget.ThresholdRatio
	if thresholdRatio == 0.0 {
		thresholdRatio = 0.85
	}

	penalty := rules.Scoring.Budget.Penalty
	if penalty == 0 {
		penalty = -3
	}

	if cost > (limit * thresholdRatio) {
		return penalty
	}
	return 0
}

func (b *BrokerServer) getModelRankScore(model string, rules *RouterRules) float64 {
	raw, ok := rules.ModelRankings[model]
	if !ok {
		return 0.0
	}
	var rank ModelRank
	if err := json.Unmarshal(raw, &rank); err != nil {
		return 0.0
	}
	return rank.RankScore
}

// getModelTier returns the tier declared in model_rankings for a model, or "" if unknown.
func (b *BrokerServer) getModelTier(model string, rules *RouterRules) string {
	raw, ok := rules.ModelRankings[model]
	if !ok {
		return ""
	}
	var rank ModelRank
	if err := json.Unmarshal(raw, &rank); err != nil {
		return ""
	}
	return rank.Tier
}

var tierNums = map[string]int{"L1": 1, "L2": 2, "L3": 3, "L4": 4}

// isTierCompatibleWith returns true if a model's declared tier can serve a request
// for requestedTier. A model is compatible only if its tier ≤ requestedTier,
// preventing heavy models from appearing in light tier candidate lists.
func isTierCompatibleWith(modelTier, requestedTier string) bool {
	if modelTier == "" || requestedTier == "" {
		return true
	}
	mNum, mOk := tierNums[modelTier]
	rNum, rOk := tierNums[requestedTier]
	if !mOk || !rOk {
		return true
	}
	return mNum <= rNum
}

func (b *BrokerServer) modelNameMatches(configModel, actualModel string) bool {
	// 1. Extract size tags from raw strings before any normalization.
	// We match numbers followed by 'b' or 'B' at word boundaries to be safe.
	extractSizeTags := func(s string) []string {
		re := regexp.MustCompile(`\b\d+(?:\.\d+)?[bB]\b`)
		matches := re.FindAllString(s, -1)
		var tags []string
		for _, m := range matches {
			tags = append(tags, strings.ToLower(m))
		}
		return tags
	}

	cSizes := extractSizeTags(configModel)
	aSizes := extractSizeTags(actualModel)

	if len(cSizes) > 0 && len(aSizes) > 0 {
		matched := false
		for _, cs := range cSizes {
			for _, as := range aSizes {
				if cs == as {
					matched = true
					break
				}
			}
			if matched {
				break
			}
		}
		if !matched {
			return false
		}
	}

	// 2. Strip size tags from raw strings before normalization to prevent merging version numbers and size tags.
	stripSizeTags := func(s string) string {
		re := regexp.MustCompile(`\b\d+(?:\.\d+)?[bB]\b`)
		return re.ReplaceAllString(s, "")
	}

	cStrippedRaw := stripSizeTags(configModel)
	aStrippedRaw := stripSizeTags(actualModel)

	norm := func(s string) string {
		s = strings.ToLower(s)
		s = strings.ReplaceAll(s, ":", "")
		s = strings.ReplaceAll(s, "-", "")
		s = strings.ReplaceAll(s, "_", "")
		s = strings.ReplaceAll(s, ".", "")
		s = strings.ReplaceAll(s, "instruct", "")
		s = strings.TrimSpace(s)
		return s
	}

	cNorm := norm(cStrippedRaw)
	aNorm := norm(aStrippedRaw)

	if cNorm == aNorm || strings.Contains(aNorm, cNorm) || strings.Contains(cNorm, aNorm) {
		return true
	}

	return false
}

type LocalCandidate struct {
	Model    string
	Provider string
}

func (b *BrokerServer) getLocalCandidates(tier string, rules *RouterRules, pulledModels map[string]string) []LocalCandidate {
	// Collect configured model names for this tier from ALL local provider sections.
	// This allows router_rules.json to list Jan/LM Studio model names alongside Ollama names.
	localProviders := []string{ProviderOllama, ProviderJan, ProviderLMStudio, ProviderLlamaCpp}
	var allConfigModels []string
	seenConfig := make(map[string]bool)
	for _, provKey := range localProviders {
		provMap := rules.Models[provKey]
		if provMap == nil {
			continue
		}
		primary := b.getStringOrFirst(provMap[tier])
		alts := b.getStringSlice(provMap[tier+"_alt"])
		for _, m := range append([]string{primary}, alts...) {
			if m != "" && !seenConfig[m] {
				seenConfig[m] = true
				allConfigModels = append(allConfigModels, m)
			}
		}
	}

	// Sort by rank score (highest first)
	sort.Slice(allConfigModels, func(i, j int) bool {
		return b.getModelRankScore(allConfigModels[i], rules) > b.getModelRankScore(allConfigModels[j], rules)
	})

	fmt.Fprintf(os.Stderr, "[DEBUG] router.getLocalCandidates: tier=%s configModels=%v pulledModels=%v\n", tier, allConfigModels, pulledModels)

	var result []LocalCandidate
	seenResult := make(map[string]bool) // dedup by "model@provider"

	for _, configModel := range allConfigModels {
		// Exact match wins first
		exactFound := false
		if provider, ok := pulledModels[configModel]; ok {
			if b.isCircuitOpen(provider) {
				fmt.Fprintf(os.Stderr, "[DEBUG] router.getLocalCandidates: SKIP exact  model=%-36s — provider %s circuit OPEN\n", configModel, provider)
				exactFound = true
				continue
			}
			// Tier compatibility check: a model ranked as "L3" in model_rankings
			// should not be selected for an L1 or L2 request even if explicitly
			// listed in that tier's config section — the ranking is authoritative.
			modelTier := b.getModelTier(configModel, rules)
			if !isTierCompatibleWith(modelTier, tier) {
				fmt.Fprintf(os.Stderr, "[DEBUG] router.getLocalCandidates: SKIP exact  model=%-36s declared-tier=%s > requested=%s\n", configModel, modelTier, tier)
			} else {
				// pulledModels was fetched live moments ago — the provider responding to
				// /v1/models IS proof of availability. Do not gate on healthCache here:
				// a stale Available=false silently blocks models that are clearly up.
				key := configModel + "@" + provider
				if !seenResult[key] {
					seenResult[key] = true
					result = append(result, LocalCandidate{Model: configModel, Provider: provider})
				}
			}
			exactFound = true // exact match present; skip fuzzy to avoid false positives
		}
		if exactFound {
			continue
		}
		// Fuzzy match only when no exact match exists — handles config names that differ
		// from the provider's reported name (e.g. Ollama short names vs Jan full names).
		for pulledModel, provider := range pulledModels {
			if b.isCircuitOpen(provider) {
				fmt.Fprintf(os.Stderr, "[DEBUG] router.getLocalCandidates: SKIP fuzzy  model=%-36s — provider %s circuit OPEN\n", configModel, provider)
				continue
			}
			if b.modelNameMatches(configModel, pulledModel) {
				// Skip models declared in a heavier tier than what we're looking for.
				pulledTier := b.getModelTier(pulledModel, rules)
				if !isTierCompatibleWith(pulledTier, tier) {
					fmt.Fprintf(os.Stderr, "[DEBUG] router.getLocalCandidates: SKIP fuzzy pulled=%-36s declared-tier=%s > requested=%s\n", pulledModel, pulledTier, tier)
					continue
				}
				// Same reasoning: pulledModels is live, no healthCache gate needed.
				key := pulledModel + "@" + provider
				if !seenResult[key] {
					seenResult[key] = true
					fmt.Fprintf(os.Stderr, "[DEBUG] router.getLocalCandidates: MATCH config=%-36s → pulled=%-36s provider=%s\n", configModel, pulledModel, provider)
					result = append(result, LocalCandidate{Model: pulledModel, Provider: provider})
				}
			}
		}
	}
	fmt.Fprintf(os.Stderr, "[DEBUG] router.getLocalCandidates: result=%d candidates\n", len(result))
	return result
}

func (b *BrokerServer) pickBestLocal(tier string, rules *RouterRules, pulledModels map[string]string) (string, string, bool) {
	candidates := b.getLocalCandidates(tier, rules, pulledModels)
	if len(candidates) == 0 {
		fmt.Fprintf(os.Stderr, "[DEBUG] router.pickBestLocal: NO candidates for tier=%s\n", tier)
		return "", "", false
	}
	fmt.Fprintf(os.Stderr, "[DEBUG] router.pickBestLocal: %d candidates for tier=%s\n", len(candidates), tier)

	// Sort by EMA latency (lowest first), then by rank score as tiebreaker
	type scoredCandidate struct {
		candidate LocalCandidate
		ema       float64
		hasEMA    bool
	}
	var scored []scoredCandidate
	for _, c := range candidates {
		health := b.getBackendHealth(c.Provider)
		sc := scoredCandidate{candidate: c, ema: health.EMAMsPerToken, hasEMA: health.TotalTokens >= EMAMinTokensForReliability}
		scored = append(scored, sc)
	}

	tierDist := func(model string) int {
		mt := b.getModelTier(model, rules)
		mNum, mOk := tierNums[mt]
		rNum, rOk := tierNums[tier]
		if !mOk || !rOk || mt == "" {
			return 0 // unknown tier: treat as exact match
		}
		d := rNum - mNum
		if d < 0 {
			d = -d
		}
		return d
	}

	sort.Slice(scored, func(i, j int) bool {
		// Both have EMA data: sort by EMA ascending
		if scored[i].hasEMA && scored[j].hasEMA {
			if scored[i].ema != scored[j].ema {
				return scored[i].ema < scored[j].ema
			}
		}
		// One has EMA, the other doesn't: prefer the one with data
		if scored[i].hasEMA != scored[j].hasEMA {
			return scored[i].hasEMA
		}
		// No EMA data: prefer the model whose declared tier is closest to the requested tier,
		// then break ties by rank_score descending.
		// This prevents a heavy L3 model from being chosen over a matching L2 model.
		distI := tierDist(scored[i].candidate.Model)
		distJ := tierDist(scored[j].candidate.Model)
		if distI != distJ {
			return distI < distJ
		}
		rankI := b.getModelRankScore(scored[i].candidate.Model, rules)
		rankJ := b.getModelRankScore(scored[j].candidate.Model, rules)
		return rankI > rankJ
	})

	// Pick lowest-latency candidate; skip candidates exceeding the EMA threshold
	for _, sc := range scored {
		if sc.hasEMA && sc.ema > EMALatencyThresholdMsPerToken {
			continue // exclude dead backend
		}
		return sc.candidate.Model, sc.candidate.Provider, true
	}

	// All candidates exceed threshold — fallback to the best-ranked one anyway
	best := scored[0]
	return best.candidate.Model, best.candidate.Provider, true
}

func (b *BrokerServer) pickBestCloud(tier string, rules *RouterRules) string {
	cloudProvider := rules.HybridRouting.CloudFallbackProvider
	cloudMap := rules.Models[cloudProvider]

	primary := b.getStringOrFirst(cloudMap[tier])
	alts := b.getStringSlice(cloudMap[tier+"_alt"])

	allCandidates := append([]string{primary}, alts...)
	for _, m := range allCandidates {
		if m != "" {
			return m
		}
	}
	return "gemini-3-flash" // Safe fallback
}

func (b *BrokerServer) getStringOrFirst(val interface{}) string {
	if str, ok := val.(string); ok {
		return str
	}
	if slice, ok := val.([]interface{}); ok && len(slice) > 0 {
		if str, ok := slice[0].(string); ok {
			return str
		}
	}
	return ""
}

func (b *BrokerServer) getStringSlice(val interface{}) []string {
	if slice, ok := val.([]interface{}); ok {
		var res []string
		for _, item := range slice {
			if str, ok := item.(string); ok {
				res = append(res, str)
			}
		}
		return res
	}
	if str, ok := val.(string); ok {
		return []string{str}
	}
	return nil
}

func (b *BrokerServer) getConfiguredLocalModels(tier string, rules *RouterRules) []string {
	localProviders := []string{ProviderOllama, ProviderJan, ProviderLMStudio, ProviderLlamaCpp}
	seen := make(map[string]bool)
	var raw []string
	for _, provKey := range localProviders {
		provMap := rules.Models[provKey]
		if provMap == nil {
			continue
		}
		primary := b.getStringOrFirst(provMap[tier])
		alts := b.getStringSlice(provMap[tier+"_alt"])
		for _, m := range append([]string{primary}, alts...) {
			if m != "" && !seen[m] {
				seen[m] = true
				raw = append(raw, m)
			}
		}
	}
	sort.Slice(raw, func(i, j int) bool {
		return b.getModelRankScore(raw[i], rules) > b.getModelRankScore(raw[j], rules)
	})
	return raw
}
