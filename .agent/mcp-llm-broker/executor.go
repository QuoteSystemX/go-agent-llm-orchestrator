package main

import (
	"bufio"
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/mark3labs/mcp-go/mcp"
)

type ExecutionResult struct {
	Response string                 `json:"response"`
	Source   string                 `json:"source"`
	Model    string                 `json:"model"`
	Stats    map[string]interface{} `json:"stats,omitempty"`
}

// localOnlyCtxKey marks a request that must NEVER fall back to the cloud provider.
// Set by invokeAgent so sub-agents always run on a local backend (Jan/Ollama) — if no
// local model is available or local execution fails, the request errors instead of
// silently escaping to cloud. This is the guarantee that delegated work stays local.
type localOnlyCtxKey struct{}

func withLocalOnly(ctx context.Context) context.Context {
	return context.WithValue(ctx, localOnlyCtxKey{}, true)
}

func isLocalOnly(ctx context.Context) bool {
	v, _ := ctx.Value(localOnlyCtxKey{}).(bool)
	return v
}

// toolsEnabledCtxKey marks a request whose sub-agent persona may use the
// sandboxed read-only tools (read_file/grep — see tools_readonly.go) to
// check a claim against the real repository instead of confabulating it.
// Deliberately independent of localOnlyCtxKey: "never escape to cloud" and
// "has tool access" are two unrelated guarantees that happened to be
// conflated by how the agentic-loop gate was originally written — a
// dispatch can be local-only AND tool-enabled at the same time (this is, in
// fact, the common case: see invokeAgent).
type toolsEnabledCtxKey struct{}

func withToolsEnabled(ctx context.Context) context.Context {
	return context.WithValue(ctx, toolsEnabledCtxKey{}, true)
}

func toolsEnabled(ctx context.Context) bool {
	v, _ := ctx.Value(toolsEnabledCtxKey{}).(bool)
	return v
}

// isTierName returns true if s is a direct tier selector (L1–L4).
func isTierName(s string) bool {
	return s == "L1" || s == "L2" || s == "L3" || s == "L4"
}

// executePromptLogic is the core execution pipeline shared by MCP and HTTP handlers.
// It routes, caches, executes, and returns a structured result.
func (b *BrokerServer) executePromptLogic(ctx context.Context, prompt, systemPrompt, difficultyHint, jsonSchema, modelOverride string, stream bool) (*ExecutionResult, error) {
	// Cancel warmup if it's running to free up Jan semaphore
	b.healthCacheMu.Lock()
	if b.warmupCancel != nil {
		b.warmupCancel()
		b.warmupCancel = nil
	}
	b.healthCacheMu.Unlock()

	// Validate JSON Schema if provided
	if jsonSchema != "" {
		if !isValidJSON(jsonSchema) {
			return nil, fmt.Errorf("json_schema is not valid JSON")
		}
	}

	// Detect direct tier override: model="L2" skips complexity scoring and goes
	// straight to the best available model for that tier.
	tierOverride := ""
	if isTierName(strings.ToUpper(modelOverride)) {
		tierOverride = strings.ToUpper(modelOverride)
		modelOverride = "" // route through makeRoutingDecision with tier pinned
		fmt.Fprintf(os.Stderr, "[DEBUG] executor: tier override detected — using tier=%s directly\n", tierOverride)
	}

	// 1. Calculate Routing Decision
	// Determine task description to route complexity
	taskDesc := difficultyHint
	if taskDesc == "" {
		taskDesc = prompt
	}

	rules, err := b.loadRules()
	if err != nil {
		return nil, fmt.Errorf("failed to load routing rules: %s", err.Error())
	}

	env := b.detectEnv()
	discoverCtx, cancel := context.WithTimeout(ctx, 3*time.Second)
	defer cancel()

	// Detect pulled models
	pulled := make(map[string]string)
	ollamaURL := b.getOllamaURL(env)
	if models, err := b.fetchOllamaModels(discoverCtx, ollamaURL); err == nil {
		for _, m := range models {
			pulled[m] = ProviderOllama
		}
		fmt.Fprintf(os.Stderr, "[DEBUG] executor: Ollama models found: %v\n", models)
	} else {
		fmt.Fprintf(os.Stderr, "[DEBUG] executor: Ollama not available: %v\n", err)
	}
	if models, err := b.fetchOpenAICompatibleModels(discoverCtx, DefaultJanURL); err == nil {
		for _, m := range models {
			pulled[m] = ProviderJan
		}
		fmt.Fprintf(os.Stderr, "[DEBUG] executor: Jan models found (local): %v\n", models)
	} else if env.IsWSL && env.WSLGateway != "" {
		wslURL := fmt.Sprintf("http://%s:1337", env.WSLGateway)
		if models, err := b.fetchOpenAICompatibleModels(discoverCtx, wslURL); err == nil {
			for _, m := range models {
				pulled[m] = ProviderJan
			}
			fmt.Fprintf(os.Stderr, "[DEBUG] executor: Jan models found (WSL gateway %s): %v\n", env.WSLGateway, models)
		} else {
			fmt.Fprintf(os.Stderr, "[DEBUG] executor: Jan not available on WSL gateway: %v\n", err)
		}
	} else {
		fmt.Fprintf(os.Stderr, "[DEBUG] executor: Jan not available locally: %v\n", err)
	}
	if models, err := b.fetchOpenAICompatibleModels(discoverCtx, DefaultLMStudioURL); err == nil {
		for _, m := range models {
			pulled[m] = ProviderLMStudio
		}
	} else if env.IsWSL && env.WSLGateway != "" {
		wslURL := fmt.Sprintf("http://%s:1234", env.WSLGateway)
		if models, err := b.fetchOpenAICompatibleModels(discoverCtx, wslURL); err == nil {
			for _, m := range models {
				pulled[m] = ProviderLMStudio
			}
		}
	}
	// Standalone llama-server — URL is user-configured (random port), not guessed.
	llamaCppURL := rules.LlamaCppBaseURL
	if llamaCppURL == "" {
		llamaCppURL = DefaultLlamaCppURL
	}
	if models, err := b.fetchOpenAICompatibleModels(discoverCtx, llamaCppURL); err == nil {
		for _, m := range models {
			pulled[m] = ProviderLlamaCpp
		}
		fmt.Fprintf(os.Stderr, "[DEBUG] executor: llama.cpp models found (%s): %v\n", llamaCppURL, models)
	} else {
		fmt.Fprintf(os.Stderr, "[DEBUG] executor: llama.cpp not available at %s: %v\n", llamaCppURL, err)
	}

	fmt.Fprintf(os.Stderr, "[DEBUG] executor: pulled models count=%d: %v\n", len(pulled), pulled)

	var decision *RoutingDecision
	if modelOverride != "" {
		provider, ok := pulled[modelOverride]
		if !ok {
			// Check loose match
			for pulledModel, p := range pulled {
				if b.modelNameMatches(modelOverride, pulledModel) {
					modelOverride = pulledModel
					provider = p
					ok = true
					break
				}
			}
		}
		if ok {
			decision = &RoutingDecision{
				ModelID:  modelOverride,
				Provider: provider,
				Tier:     "override",
			}
		} else {
			// Fallback to cloud if not found locally
			decision = &RoutingDecision{
				ModelID:  modelOverride,
				Provider: rules.HybridRouting.CloudFallbackProvider,
				Tier:     "override",
			}
			if isHardwareMemoryLimitOk(modelOverride) {
				b.triggerBackgroundPull(modelOverride, rules, env)
			}
		}
	} else {
		var err error
		decision, err = b.makeRoutingDecision(taskDesc, pulled, tierOverride)
		if err != nil {
			return nil, fmt.Errorf("failed to make routing decision: %s", err.Error())
		}
		// Bump tiers based on system prompt signals (only when not explicitly overridden).
		if tierOverride == "" {
			// L1 + large system prompt → L2 for buffered (non-orchestrator) path only.
			// Orchestrator context uses the agentic loop which trims the prompt to ~37KB,
			// so Jan-4B can handle it. Bumping here would route "обнови readme" (score=0)
			// to DeepSeek-8B unnecessarily.
			if decision.Tier == "L1" && len(systemPrompt) > 500 && !isOrchestratorContext(systemPrompt) {
				fmt.Fprintf(os.Stderr, "[DEBUG] executor: bumping L1→L2 due to large system prompt (%d chars)\n", len(systemPrompt))
				decision, err = b.makeRoutingDecision(taskDesc, pulled, "L2")
				if err != nil {
					return nil, fmt.Errorf("failed to make routing decision: %s", err.Error())
				}
			}
			// Orchestrator / multi-agent context → force L3, but ONLY for complex tasks.
			// Simple conversational inputs ("привет", "как дела?") must NOT hit the 27B
			// agentic loop — they should be answered cheaply by the L2 model directly.
			// isComplexEnoughForAgenticLoop gates this with a bilingual keyword check.
			if decision.Tier != "L3" && decision.Tier != "L4" &&
				isOrchestratorContext(systemPrompt) &&
				isComplexEnoughForAgenticLoop(taskDesc) {
				fmt.Fprintf(os.Stderr, "[DEBUG] executor: bumping to L3 — orchestrator context + complex task detected\n")
				decision, err = b.makeRoutingDecision(taskDesc, pulled, "L3")
				if err != nil {
					return nil, fmt.Errorf("failed to make routing decision: %s", err.Error())
				}
			}
		}
	}

	// 1b. Inject dynamic rules
	var loader RuleLoaderPort = NewFileRuleLoaderAdapter(b.workspaceRoot)
	injectedPrompt, err := loader.LoadRules(systemPrompt, prompt, decision.Tier)
	if err == nil {
		systemPrompt = injectedPrompt
		fmt.Fprintf(os.Stderr, "[DEBUG] executor: dynamically injected rules (tier=%s), final sysPromptLen=%d\n", decision.Tier, len(systemPrompt))
	} else {
		fmt.Fprintf(os.Stderr, "[WARN] executor: failed to inject dynamic rules: %v\n", err)
	}

	// 2. Token Saving Middleware (Pre-processing)
	processedPrompt := b.runPreprocessMiddleware(prompt)

	// 3. Caching Middleware (Check cache)
	cacheKey := b.getCacheKey(processedPrompt, systemPrompt, decision.ModelID)
	if cachedResponse, ok := b.checkCache(cacheKey); ok {
		return &ExecutionResult{
			Response: cachedResponse,
			Source:   "cache",
			Model:    decision.ModelID,
			Stats: map[string]interface{}{
				"cached": true,
			},
		}, nil
	}

	// 3b. Semantic Caching
	var promptEmbedding []float64
	if rules.SemanticCache.Enabled {
		baseURL := b.getExecutionURL(ctx, decision.Provider, env, rules)
		emb, embErr := b.fetchEmbedding(ctx, decision.Provider, baseURL, decision.ModelID, processedPrompt)
		if embErr == nil {
			promptEmbedding = emb
			entries, cacheErr := b.loadSemanticCache()
			if cacheErr == nil {
				var bestMatch *SemanticCacheEntry
				bestScore := 0.0
				for _, entry := range entries {
					if entry.Model == decision.ModelID {
						similarity := cosineSimilarity(promptEmbedding, entry.Embedding)
						if similarity > bestScore {
							bestScore = similarity
							entryCopy := entry
							bestMatch = &entryCopy
						}
					}
				}

				threshold := rules.SemanticCache.Threshold
				if threshold <= 0.0 {
					threshold = 0.95
				}

				if bestMatch != nil && bestScore >= threshold {
					return &ExecutionResult{
						Response: bestMatch.Response,
						Source:   "semantic-cache",
						Model:    decision.ModelID,
						Stats: map[string]interface{}{
							"cached":     true,
							"similarity": bestScore,
						},
					}, nil
				}
			}
		}
	}

	// Budget check before cloud execution
	if decision.Provider == rules.HybridRouting.CloudFallbackProvider || modelOverride == "" {
		if b.isBudgetExceeded(rules) {
			return nil, fmt.Errorf("cloud execution blocked: budget limit exceeded in watchdog_rules.json")
		}
	}

	// 4. Execution (Proxy LLM call with local retries if needed)
	var responseText string
	var executionErr error
	var finalProvider string
	var finalModel string

	// No per-tier output cap — model generates until end_turn.
	// Jan's n_ctx (set in model settings) is the effective ceiling.
	maxTokens := 32768
	if rules.ProviderSettings != nil {
		if ps, ok := rules.ProviderSettings["jan"]; ok && ps.NCtx > 0 {
			maxTokens = ps.NCtx
		}
	}

	// Helper to call with JSON schema retry logic.
	// When jsonSchema is empty, 0 retries (fail fast, try next candidate).
	// When jsonSchema is set, up to maxRetries attempts with rising temperature.
	executeWithSchemaRetry := func(model, provider, baseURL, prompt, systemPrompt string, jsonSchema string, stream bool, maxRetries int) (string, error) {
		var lastErr error
		retries := maxRetries
		if jsonSchema == "" {
			retries = 0
		}
		for attempt := 0; attempt <= retries; attempt++ {
			temp := 0.1 + float64(attempt)*0.2
			resp, err := b.executeLLMCall(ctx, model, provider, baseURL, prompt, systemPrompt, jsonSchema, stream, temp, maxTokens)
			if err != nil {
				lastErr = err
				continue
			}
			if jsonSchema != "" {
				if !isValidJSON(resp) {
					lastErr = fmt.Errorf("response is not valid JSON (attempt %d)", attempt)
					continue
				}
			}
			return resp, nil
		}
		return "", fmt.Errorf("all %d retries exhausted: %w", retries, lastErr)
	}

	// useAgenticLoop: all orchestrator context requests use the agentic loop so
	// they always get the minimal trimmed system prompt and real-time SSE streaming.
	// Sending the full 125KB orchestrator prompt to an L2 model via the buffered path
	// causes the model to follow the orchestrator.md initialization protocol literally
	// and emit structured metadata junk instead of answering the user.
	// isComplexEnoughForAgenticLoop is still used to gate the L3 model bump and the
	// forced call_agent on iter=0 — simple queries like "привет" use tool_choice:auto
	// and typically return end_turn in a single iteration.
	orchCtx := isOrchestratorContext(systemPrompt)
	useAgenticLoop := jsonSchema == "" && orchCtx
	fmt.Fprintf(os.Stderr, "[DEBUG] executePromptLogic: sysPromptLen=%d orchCtx=%v useAgenticLoop=%v jsonSchema=%q localOnly=%v\n",
		len(systemPrompt), orchCtx, useAgenticLoop, jsonSchema, isLocalOnly(ctx))
	if len(systemPrompt) > 0 {
		scanEnd := 200
		if len(systemPrompt) < scanEnd {
			scanEnd = len(systemPrompt)
		}
		fmt.Fprintf(os.Stderr, "[DEBUG] sysPrompt[:200]=%q\n", systemPrompt[:scanEnd])
	}

	// Orchestrator agentic loop — runs on local L3 (Jan/Qwen3-27B).
	// The L3 decision was already computed and tier-bumped above; re-use it so the
	// loop hits the same Jan endpoint that the rest of execution uses.
	// isLocalOnly(ctx) is set by invokeAgent for sub-agents — they must never reach here.
	if useAgenticLoop && !isLocalOnly(ctx) {
		loopProvider := decision.Provider
		loopModel := decision.ModelID
		loopURL := b.getExecutionURL(ctx, loopProvider, env, rules)
		fmt.Fprintf(os.Stderr, "[INFO] executor: orchestrator → local agentic loop (provider=%s model=%s url=%s)\n",
			loopProvider, loopModel, loopURL)
		resp, aerr := b.executeAgenticLoop(ctx, processedPrompt, systemPrompt, loopModel, loopProvider, loopURL, maxTokens, decision.Score, decision.Tier)
		if aerr != nil {
			return nil, fmt.Errorf("orchestrator agentic loop failed: %w", aerr)
		}
		b.saveCache(cacheKey, resp)
		return &ExecutionResult{Response: resp, Source: loopProvider, Model: loopModel}, nil
	}

	// Sub-agent tool-calling: local-only dispatches (invokeAgent) that asked
	// for tool access. Independent of useAgenticLoop/orchCtx — GUARANTEE C
	// (never escape to cloud) is still enforced entirely by isLocalOnly;
	// this only adds sandboxed read_file/grep access on top of it. Only
	// Ollama is wired up natively here (executeAgenticLoop's Jan/Anthropic
	// tool format is a different wire protocol and out of this card's
	// scope — see task card §2) — if no Ollama candidate is available this
	// falls through to the normal buffered (no-tool) path below unchanged.
	if jsonSchema == "" && isLocalOnly(ctx) && toolsEnabled(ctx) && !orchCtx {
		for _, c := range b.getLocalCandidates(decision.Tier, rules, pulled) {
			if c.Provider != ProviderOllama || b.isCircuitOpen(c.Provider) {
				continue
			}
			baseURL := b.getExecutionURL(ctx, ProviderOllama, env, rules)
			fmt.Fprintf(os.Stderr, "[INFO] executor: sub-agent tool loop (provider=%s model=%s url=%s)\n", ProviderOllama, c.Model, baseURL)
			resp, toolLog, terr := b.executeOllamaToolLoop(ctx, processedPrompt, systemPrompt, c.Model, baseURL, maxTokens, rules)
			if terr != nil {
				// Try the next Ollama candidate (if any) before giving up on tools
				// entirely — a transient failure or exhausted iteration budget on
				// one model shouldn't skip tool access when another candidate
				// exists. Falls through to the buffered no-tool path only once
				// every candidate has been tried.
				fmt.Fprintf(os.Stderr, "[WARN] executor: sub-agent tool loop failed for model=%s (%v) — trying next candidate\n", c.Model, terr)
				continue
			}
			b.saveCache(cacheKey, resp)
			return &ExecutionResult{
				Response: resp,
				Source:   ProviderOllama,
				Model:    c.Model,
				Stats:    map[string]interface{}{"tool_calls": toolLog},
			}, nil
		}
	}

	if modelOverride != "" {
		// If overridden, just try that model
		if b.isCircuitOpen(decision.Provider) {
			return nil, fmt.Errorf("cannot execute overridden model %s: provider %s circuit is OPEN", decision.ModelID, decision.Provider)
		}
		baseURL := b.getExecutionURL(ctx, decision.Provider, env, rules)
		fmt.Fprintf(os.Stderr, "[DEBUG] executor: modelOverride path — model=%s, provider=%s, tier=%s, baseURL=%s\n", decision.ModelID, decision.Provider, decision.Tier, baseURL)
		responseText, executionErr = executeWithSchemaRetry(decision.ModelID, decision.Provider, baseURL, processedPrompt, systemPrompt, jsonSchema, stream, 2)
		finalProvider = decision.Provider
		finalModel = decision.ModelID
	} else {
		// Try local candidates in order
		fmt.Fprintf(os.Stderr, "[DEBUG] executor: auto-routing path — decision tier=%s, modelID=%s, provider=%s, score=%d\n", decision.Tier, decision.ModelID, decision.Provider, decision.Score)
		candidates := b.getLocalCandidates(decision.Tier, rules, pulled)
		fmt.Fprintf(os.Stderr, "[DEBUG] executor: getLocalCandidates returned %d candidates\n", len(candidates))
		for i, c := range candidates {
			fmt.Fprintf(os.Stderr, "[DEBUG] executor:   candidate[%d]: model=%s provider=%s\n", i, c.Model, c.Provider)
		}

		// If decision is to use cloud directly
		if decision.Provider == rules.HybridRouting.CloudFallbackProvider {
			// GUARANTEE C — sub-agents are local-only. If routing chose cloud for a
			// local-only request (e.g. no local model for this tier), error instead of
			// escaping to cloud.
			if isLocalOnly(ctx) {
				return nil, fmt.Errorf("local-only request routed to cloud (%s tier=%s) — no local model available; refusing cloud", decision.ModelID, decision.Tier)
			}
			baseURL := b.getExecutionURL(ctx, decision.Provider, env, rules)
			responseText, executionErr = executeWithSchemaRetry(decision.ModelID, decision.Provider, baseURL, processedPrompt, systemPrompt, jsonSchema, stream, 2)
			finalProvider = decision.Provider
			finalModel = decision.ModelID
		} else {
			// Try local candidates
			if len(candidates) == 0 {
				executionErr = fmt.Errorf("no healthy local candidates available")
				finalProvider = decision.Provider
				finalModel = decision.ModelID
			} else {
				skippedAll := true
				for i, cand := range candidates {
					if b.isCircuitOpen(cand.Provider) {
						fmt.Fprintf(os.Stderr, "[DEBUG] executor: SKIP candidate[%d] model=%s — провайдер %s circuit OPEN\n", i, cand.Model, cand.Provider)
						continue
					}
					skippedAll = false
					baseURL := b.getExecutionURL(ctx, cand.Provider, env, rules)
					fmt.Fprintf(os.Stderr, "[DEBUG] executor: trying candidate[%d] model=%s provider=%s baseURL=%s\n", i, cand.Model, cand.Provider, baseURL)
					responseText, executionErr = executeWithSchemaRetry(cand.Model, cand.Provider, baseURL, processedPrompt, systemPrompt, jsonSchema, stream, 2)
					if executionErr == nil {
						finalProvider = cand.Provider
						finalModel = cand.Model
						fmt.Fprintf(os.Stderr, "[DEBUG] executor: candidate[%d] succeeded — model=%s provider=%s\n", i, cand.Model, cand.Provider)
						break
					}
					// Log retry info if we failed but have more candidates
					if i < len(candidates)-1 {
						fmt.Fprintf(os.Stderr, "[DEBUG] executor: candidate[%d] FAILED: %s. Retrying next...\n", i, executionErr.Error())
					} else {
						fmt.Fprintf(os.Stderr, "[DEBUG] executor: candidate[%d] FAILED (last): %s\n", i, executionErr.Error())
					}
				}
				if skippedAll {
					executionErr = fmt.Errorf("all local candidates skipped because their circuits are OPEN")
					finalProvider = decision.Provider
					finalModel = decision.ModelID
				}
			}
		}
	}

	if executionErr != nil {
		fmt.Fprintf(os.Stderr, "[DEBUG] executor: execution error — %s (finalProvider=%s finalModel=%s)\n", executionErr.Error(), finalProvider, finalModel)

		// GUARANTEE C — sub-agents are local-only: never fall back to cloud on local failure.
		if isLocalOnly(ctx) {
			return nil, fmt.Errorf("local-only execution failed and cloud fallback is disabled: %s", executionErr.Error())
		}

		// Fallback to Cloud if local execution fails
		if finalProvider != rules.HybridRouting.CloudFallbackProvider {
			cloudProvider := rules.HybridRouting.CloudFallbackProvider

			// Check budget before cloud fallback
			if b.isBudgetExceeded(rules) {
				return nil, fmt.Errorf("cloud fallback blocked: budget limit exceeded. Local error: %s", executionErr.Error())
			}

			cloudModel := b.pickBestCloud(decision.Tier, rules)
			cloudURL := b.getExecutionURL(ctx, cloudProvider, env, rules)

			fallbackResponse, errFb := executeWithSchemaRetry(cloudModel, cloudProvider, cloudURL, processedPrompt, systemPrompt, jsonSchema, stream, 2)
			if errFb == nil {
				// Cache fallback response
				b.saveCache(cacheKey, fallbackResponse)

				return &ExecutionResult{
					Response: fallbackResponse,
					Source:   cloudProvider,
					Model:    cloudModel,
					Stats: map[string]interface{}{
						"fallback_triggered": true,
						"local_error":        executionErr.Error(),
					},
				}, nil
			}
		}
		return nil, fmt.Errorf("execution failed: %s", executionErr.Error())
	}

	// 5. Caching Middleware (Save cache)
	b.saveCache(cacheKey, responseText)
	if promptEmbedding != nil {
		b.saveSemanticCacheEntry(cacheKey, SemanticCacheEntry{
			Prompt:    processedPrompt,
			Response:  responseText,
			Model:     finalModel,
			Embedding: promptEmbedding,
		})
	}

	return &ExecutionResult{
		Response: responseText,
		Source:   finalProvider,
		Model:    finalModel,
	}, nil
}

// handleExecutePrompt is the MCP tool wrapper that calls executePromptLogic.
func (b *BrokerServer) handleExecutePrompt(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	prompt, _ := req.RequireString("prompt")
	systemPrompt := b.getStringArg(req.Params.Arguments, "system_prompt")
	difficultyHint := b.getStringArg(req.Params.Arguments, "difficulty_hint")
	jsonSchema := b.getStringArg(req.Params.Arguments, "json_schema")
	modelOverride := b.getStringArg(req.Params.Arguments, "model")

	stream := b.getBoolArgDefault(req.Params.Arguments, "stream", false)

	res, err := b.executePromptLogic(ctx, prompt, systemPrompt, difficultyHint, jsonSchema, modelOverride, stream)
	if err != nil {
		return mcp.NewToolResultError(err.Error()), nil
	}

	jsonData, _ := json.MarshalIndent(res, "", "  ")
	return mcp.NewToolResultText(string(jsonData)), nil
}

func (b *BrokerServer) getExecutionURL(ctx context.Context, provider string, env EnvironmentInfo, rules *RouterRules) string {
	if b.urlOverrides != nil {
		if override, ok := b.urlOverrides[provider]; ok {
			return override
		}
	}

	// Cloud fallback provider (antigravity, etc.) — direct URL, no proxy
	if provider == rules.HybridRouting.CloudFallbackProvider {
		// Cloud provider API endpoints — no Ollama fallback
		return b.getCloudURL(provider, rules)
	}

	// Ollama — direct
	if provider == ProviderOllama || provider == "ollama" {
		return b.getOllamaURL(env)
	}

	// Local OpenAI-compatible providers — try localhost first, then WSL gateway.
	// Use the configured health timeout so all local providers get the same budget.
	localTimeoutMs := rules.Timeouts.HealthMs
	if localTimeoutMs <= 0 {
		localTimeoutMs = rules.HybridRouting.OllamaHealthTimeoutMs
	}
	if localTimeoutMs <= 0 {
		localTimeoutMs = 1500
	}
	localTimeout := time.Duration(localTimeoutMs) * time.Millisecond

	if provider == ProviderJan {
		if env.IsWSL && env.WSLGateway != "" {
			wslURL := fmt.Sprintf("http://%s:1337", env.WSLGateway)
			reqCtx, cancel := context.WithTimeout(ctx, localTimeout)
			if _, err := b.fetchOpenAICompatibleModels(reqCtx, wslURL); err == nil {
				cancel()
				return wslURL
			}
			cancel()
		}
		return DefaultJanURL
	}
	if provider == ProviderLMStudio {
		if env.IsWSL && env.WSLGateway != "" {
			reqCtx, cancel := context.WithTimeout(ctx, localTimeout)
			if _, err := b.fetchOpenAICompatibleModels(reqCtx, DefaultLMStudioURL); err != nil {
				wslURL := fmt.Sprintf("http://%s:1234", env.WSLGateway)
				if _, err2 := b.fetchOpenAICompatibleModels(reqCtx, wslURL); err2 == nil {
					cancel()
					return wslURL
				}
			}
			cancel()
		}
		return DefaultLMStudioURL
	}
	if provider == ProviderLlamaCpp {
		// No WSL-gateway guessing here: a standalone llama-server's port is not a
		// fixed default, so the configured URL must already be the correct, fully
		// reachable address (WSL gateway IP included, if that's what's needed).
		if rules.LlamaCppBaseURL != "" {
			return rules.LlamaCppBaseURL
		}
		return DefaultLlamaCppURL
	}

	// Unknown provider — default to Ollama
	return b.getOllamaURL(env)
}

// getCloudURL returns the API URL for a cloud provider.
// By default, antigravity uses the standard antigravity API endpoint.
func (b *BrokerServer) getCloudURL(provider string, rules *RouterRules) string {
	// If the provider has a configured API URL, use it
	if rules.HybridRouting.CloudFallbackProvider == provider {
		// Default antigravity endpoint (no /v1 — OpenAI handler appends it)
		return "https://api.antigravity.io"
	}
	return ""
}

func (b *BrokerServer) executeLLMCall(ctx context.Context, model string, provider string, baseURL string, prompt string, systemPrompt string, jsonSchema string, stream bool, temperature float64, maxTokens int) (content string, err error) {
	rules, errRules := b.loadRules()
	var limit int
	if errRules == nil {
		limit = b.getConcurrencyLimit(provider, rules)
	} else {
		limit = 4
	}
	release, errSem := b.acquireSemaphore(ctx, provider, limit)
	if errSem != nil {
		return "", fmt.Errorf("concurrency limit reached/timeout for provider %s: %w", provider, errSem)
	}
	defer release()

	defer func() {
		if err != nil {
			if ctx.Err() == context.Canceled {
				return
			}
			b.recordProviderFailure(provider)
		} else {
			b.recordProviderSuccess(provider)
		}
	}()

	// No system prompt truncation — context window is configured by the user in Jan/Ollama.

	genTimeout := 300 * time.Second
	if rules != nil && rules.Timeouts.GenerationS > 0 {
		genTimeout = time.Duration(rules.Timeouts.GenerationS) * time.Second
	}
	ctx, cancel := context.WithTimeout(ctx, genTimeout)
	defer cancel()

	client := b.clientSlow
	if client == nil {
		client = &http.Client{Timeout: genTimeout}
	}
	startTime := time.Now()

	if provider == ProviderOllama || strings.Contains(baseURL, OllamaDefaultPortStr) {
		// Ollama native API: /api/generate
		url := fmt.Sprintf("%s/api/generate", baseURL)
		ollamaNCtx, _, _ := rules.GetProviderCtx(ProviderOllama)
		opts := map[string]interface{}{
			"temperature": temperature,
			"num_ctx":     ollamaNCtx,
		}
		if maxTokens > 0 {
			opts["num_predict"] = maxTokens
		}
		payload := map[string]interface{}{
			"model":   model,
			"prompt":  prompt,
			"stream":  stream,
			"options": opts,
		}
		if systemPrompt != "" {
			payload["system"] = systemPrompt
		}
		// JSON Schema enforcement for Ollama
		if jsonSchema != "" {
			if jsonSchema == "{}" {
				payload["format"] = "json"
			} else {
				var formatObj interface{}
				if err := json.Unmarshal([]byte(jsonSchema), &formatObj); err == nil {
					payload["format"] = formatObj
				}
			}
		}

		jsonData, err := json.Marshal(payload)
		if err != nil {
			return "", err
		}

		req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewBuffer(jsonData))
		if err != nil {
			return "", err
		}
		req.Header.Set("Content-Type", "application/json")

		resp, err := client.Do(req)
		if err != nil {
			return "", err
		}
		defer resp.Body.Close()

		if resp.StatusCode != http.StatusOK {
			bodyBytes, _ := io.ReadAll(resp.Body)
			return "", fmt.Errorf("status code %d: %s", resp.StatusCode, string(bodyBytes))
		}

		if stream {
			var fullResponse strings.Builder
			var tokenCount int
			scanner := bufio.NewScanner(resp.Body)
			for scanner.Scan() {
				line := scanner.Bytes()
				if len(line) == 0 {
					continue
				}
				var chunk struct {
					Response string `json:"response"`
					Done     bool   `json:"done"`
				}
				if err := json.Unmarshal(line, &chunk); err == nil {
					if chunk.Response != "" {
						fullResponse.WriteString(chunk.Response)
						tokenCount++
						if b.isCLI {
							fmt.Print(chunk.Response)
							_ = os.Stdout.Sync()
						}
					}
				}
			}
			if b.isCLI {
				fmt.Println()
			}
			elapsed := time.Since(startTime)
			b.updateEMALatency(provider, elapsed, tokenCount)
			b.updateTelemetryAfterCall(provider, model, prompt, fullResponse.String(), tokenCount)
			return fullResponse.String(), nil
		}

		var ollamaResp struct {
			Response  string `json:"response"`
			EvalCount int    `json:"eval_count"`
			EvalDur   int64  `json:"eval_duration"` // nanoseconds
		}
		if err := json.NewDecoder(resp.Body).Decode(&ollamaResp); err != nil {
			return "", err
		}

		elapsed := time.Since(startTime)
		evalCount := ollamaResp.EvalCount
		if evalCount == 0 {
			evalCount = estimateTokenCount(ollamaResp.Response)
		}
		b.updateEMALatency(provider, elapsed, evalCount)
		b.updateTelemetryAfterCall(provider, model, prompt, ollamaResp.Response, evalCount)
		return ollamaResp.Response, nil
	}

	// Jan uses Anthropic /messages — independent from the /v1/chat/completions queue.
	if provider == ProviderJan {
		url := fmt.Sprintf("%s/v1/messages", baseURL)

		janCall := func(sysPrompt string, outTokens int) (*http.Response, error) {
			payload := map[string]interface{}{
				"model":    model,
				"messages": []map[string]string{{"role": "user", "content": prompt}},
				"stream":   stream,
			}
			if outTokens > 0 {
				payload["max_tokens"] = outTokens
			}
			if sysPrompt != "" {
				payload["system"] = sysPrompt
			}
			data, mErr := json.Marshal(payload)
			if mErr != nil {
				return nil, mErr
			}
			r, rErr := http.NewRequestWithContext(ctx, "POST", url, bytes.NewBuffer(data))
			if rErr != nil {
				return nil, rErr
			}
			r.Header.Set("Content-Type", "application/json")
			r.Header.Set("anthropic-version", "2023-06-01")
			return client.Do(r)
		}

		resp, err := janCall(systemPrompt, maxTokens)
		if err != nil {
			return "", err
		}

		// On context overflow: trim system prompt once and retry.
		if resp.StatusCode == http.StatusBadRequest {
			bodyBytes, _ := io.ReadAll(resp.Body)
			resp.Body.Close()
			if ce := parseJanContextError(bodyBytes); ce != nil {
				excess := ce.NPromptTokens - ce.NCtx + 512
				trimmedSys := trimSystemPromptByTokens(systemPrompt, excess)
				newMaxTokens := ce.NCtx / 4
				fmt.Fprintf(os.Stderr, "[WARN] executeLLMCall Jan: context exceeded n_ctx=%d n_prompt=%d — retrying with trimmed system prompt (-%d tokens)\n",
					ce.NCtx, ce.NPromptTokens, excess)
				resp, err = janCall(trimmedSys, newMaxTokens)
				if err != nil {
					return "", err
				}
			} else {
				return "", fmt.Errorf("status code %d: %s", resp.StatusCode, string(bodyBytes))
			}
		}

		defer resp.Body.Close()

		if resp.StatusCode != http.StatusOK {
			bodyBytes, _ := io.ReadAll(resp.Body)
			return "", fmt.Errorf("status code %d: %s", resp.StatusCode, string(bodyBytes))
		}

		if stream {
			var fullResponse strings.Builder
			var tokenCount int
			scanner := bufio.NewScanner(resp.Body)
			scanner.Buffer(make([]byte, 64*1024), 64*1024)
			var lastEvent string
			for scanner.Scan() {
				line := strings.TrimSpace(scanner.Text())
				if strings.HasPrefix(line, "event: ") {
					lastEvent = strings.TrimPrefix(line, "event: ")
					if lastEvent == "message_stop" {
						break
					}
					continue
				}
				if lastEvent != "content_block_delta" || !strings.HasPrefix(line, "data: ") {
					continue
				}
				var delta struct {
					Delta struct {
						Text string `json:"text"`
					} `json:"delta"`
				}
				if json.Unmarshal([]byte(strings.TrimPrefix(line, "data: ")), &delta) == nil && delta.Delta.Text != "" {
					fullResponse.WriteString(delta.Delta.Text)
					tokenCount++
					if b.isCLI {
						fmt.Print(delta.Delta.Text)
						_ = os.Stdout.Sync()
					}
				}
			}
			if b.isCLI {
				fmt.Println()
			}
			// Strip think blocks from full response (not per-token, to preserve spacing).
			result := stripThinkBlocks(fullResponse.String())
			elapsed := time.Since(startTime)
			b.updateEMALatency(provider, elapsed, tokenCount)
			b.updateTelemetryAfterCall(provider, model, prompt, result, tokenCount)
			return result, nil
		}

		// Non-streaming: parse Anthropic response format.
		var anthropicResp struct {
			Content []struct {
				Type string `json:"type"`
				Text string `json:"text"`
			} `json:"content"`
			Usage *struct {
				OutputTokens int `json:"output_tokens"`
			} `json:"usage,omitempty"`
		}
		if err := json.NewDecoder(resp.Body).Decode(&anthropicResp); err != nil {
			return "", fmt.Errorf("decode response: %w", err)
		}
		var content string
		for _, block := range anthropicResp.Content {
			if block.Type == "text" {
				content += block.Text
			}
		}
		content = stripThinkBlocks(content)
		if content == "" {
			return "", fmt.Errorf("empty content in Jan response")
		}
		elapsed := time.Since(startTime)
		evalCount := 0
		if anthropicResp.Usage != nil {
			evalCount = anthropicResp.Usage.OutputTokens
		}
		b.updateEMALatency(provider, elapsed, evalCount)
		b.updateTelemetryAfterCall(provider, model, prompt, content, evalCount)
		return content, nil
	}

	// OpenAI compatible API: /v1/chat/completions
	url := fmt.Sprintf("%s/v1/chat/completions", baseURL)
	messages := []map[string]string{}
	if systemPrompt != "" {
		messages = append(messages, map[string]string{
			"role":    "system",
			"content": systemPrompt,
		})
	}
	messages = append(messages, map[string]string{
		"role":    "user",
		"content": prompt,
	})

	payload := map[string]interface{}{
		"model":       model,
		"messages":    messages,
		"temperature": temperature,
		"stream":      stream,
	}
	if maxTokens > 0 {
		payload["max_tokens"] = maxTokens
	}
	// JSON Schema enforcement for OpenAI-compatible
	if jsonSchema != "" {
		if jsonSchema == "{}" {
			payload["response_format"] = map[string]interface{}{
				"type": "json_object",
			}
		} else {
			var schemaObj interface{}
			if err := json.Unmarshal([]byte(jsonSchema), &schemaObj); err == nil {
				payload["response_format"] = map[string]interface{}{
					"type":   "json_schema",
					"schema": schemaObj,
				}
			}
		}
	}

	jsonData, err := json.Marshal(payload)
	if err != nil {
		return "", err
	}

	req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewBuffer(jsonData))
	if err != nil {
		return "", err
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := client.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		bodyBytes, _ := io.ReadAll(resp.Body)
		return "", fmt.Errorf("status code %d: %s", resp.StatusCode, string(bodyBytes))
	}

	if stream {
		var fullResponse strings.Builder
		var tokenCount int
		scanner := bufio.NewScanner(resp.Body)
		for scanner.Scan() {
			line := scanner.Text()
			line = strings.TrimSpace(line)
			if line == "" {
				continue
			}
			if line == "data: [DONE]" {
				break
			}
			if strings.HasPrefix(line, "data: ") {
				jsonData := strings.TrimPrefix(line, "data: ")
				var chunk struct {
					Choices []struct {
						Delta struct {
							Content string `json:"content"`
						} `json:"delta"`
					} `json:"choices"`
				}
				if err := json.Unmarshal([]byte(jsonData), &chunk); err == nil {
					if len(chunk.Choices) > 0 && chunk.Choices[0].Delta.Content != "" {
						content := chunk.Choices[0].Delta.Content
						fullResponse.WriteString(content)
						tokenCount++
						if b.isCLI {
							fmt.Print(content)
							_ = os.Stdout.Sync()
						}
					}
				}
			}
		}
		if b.isCLI {
			fmt.Println()
		}
		elapsed := time.Since(startTime)
		b.updateEMALatency(provider, elapsed, tokenCount)
		b.updateTelemetryAfterCall(provider, model, prompt, fullResponse.String(), tokenCount)
		return fullResponse.String(), nil
	}

	var openaiResp struct {
		Choices []struct {
			Message struct {
				// content can be a string, null, or an array of content parts (thinking models)
				Content          json.RawMessage `json:"content"`
				ReasoningContent string          `json:"reasoning_content"`
			} `json:"message"`
		} `json:"choices"`
		Usage *struct {
			PromptTokens     int `json:"prompt_tokens"`
			CompletionTokens int `json:"completion_tokens"`
			TotalTokens      int `json:"total_tokens"`
		} `json:"usage,omitempty"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&openaiResp); err != nil {
		return "", fmt.Errorf("decode response: %w", err)
	}

	if len(openaiResp.Choices) > 0 {
		var content string
		raw := openaiResp.Choices[0].Message.Content
		if len(raw) > 0 && string(raw) != "null" {
			if err := json.Unmarshal(raw, &content); err != nil {
				// content is an array of content parts — extract text values
				var parts []map[string]interface{}
				if err2 := json.Unmarshal(raw, &parts); err2 == nil {
					for _, part := range parts {
						if t, ok := part["text"].(string); ok {
							content += t
						}
					}
				}
			}
		}
		// Some thinking models (DeepSeek, Qwen) return the visible answer in
		// reasoning_content when content is null or empty.
		if content == "" && openaiResp.Choices[0].Message.ReasoningContent != "" {
			content = openaiResp.Choices[0].Message.ReasoningContent
		}
		if content == "" {
			return "", fmt.Errorf("empty content in response choices")
		}

		elapsed := time.Since(startTime)
		evalCount := 0
		if openaiResp.Usage != nil && openaiResp.Usage.CompletionTokens > 0 {
			evalCount = openaiResp.Usage.CompletionTokens
		} else {
			evalCount = estimateTokenCount(content)
		}
		b.updateEMALatency(provider, elapsed, evalCount)
		b.updateTelemetryAfterCall(provider, model, prompt, content, evalCount)
		return content, nil
	}

	return "", fmt.Errorf("empty response choices")
}

// isValidJSON checks if a string is valid JSON
func isValidJSON(s string) bool {
	var js interface{}
	return json.Unmarshal([]byte(s), &js) == nil
}

// estimateTokenCount approximates token count from text length
func estimateTokenCount(text string) int {
	// Rough estimate: ~4 chars per token for most models
	return len([]rune(text)) / 4
}

// updateEMALatency updates the Exponential Moving Average of ms/token for a provider
func (b *BrokerServer) updateEMALatency(provider string, elapsed time.Duration, tokenCount int) {
	if tokenCount <= 0 {
		tokenCount = 1
	}
	msPerToken := float64(elapsed.Milliseconds()) / float64(tokenCount)

	b.healthCacheMu.Lock()
	defer b.healthCacheMu.Unlock()

	if b.healthCache == nil {
		b.healthCache = make(map[string]BackendHealth)
	}

	h, ok := b.healthCache[provider]
	if !ok {
		h = BackendHealth{Available: true}
	}

	if h.TotalTokens < EMAMinTokensForReliability {
		// Cold start: use simple average until we have enough samples
		totalMs := h.EMAMsPerToken * float64(h.TotalTokens)
		h.TotalTokens += int64(tokenCount)
		h.EMAMsPerToken = (totalMs + msPerToken*float64(tokenCount)) / float64(h.TotalTokens)
	} else {
		// EMA update: new_ema = alpha * current + (1 - alpha) * old_ema
		h.EMAMsPerToken = EMAAlpha*msPerToken + (1-EMAAlpha)*h.EMAMsPerToken
		h.TotalTokens += int64(tokenCount)
	}
	h.Available = true
	h.Latency = elapsed
	h.LastCheck = time.Now()
	b.healthCache[provider] = h
}

// TelemetryEntry represents a single cost entry in telemetry.json
type TelemetryEntry struct {
	Timestamp    string  `json:"timestamp"`
	Provider     string  `json:"provider"`
	Model        string  `json:"model"`
	InputTokens  int     `json:"input_tokens"`
	OutputTokens int     `json:"output_tokens"`
	CostUSD      float64 `json:"cost_usd"`
}

// updateTelemetryAfterCall records token usage and cost in telemetry.json
func (b *BrokerServer) updateTelemetryAfterCall(provider string, model string, prompt string, response string, outputTokens int) {
	// Only track cloud costs; local is free
	pricing, ok := DefaultProviderPrices[provider]
	if !ok || (pricing.InputPricePer1K == 0 && pricing.OutputPricePer1K == 0) {
		return
	}

	inputTokens := estimateTokenCount(prompt)
	cost := (float64(inputTokens)/1000.0)*pricing.InputPricePer1K +
		(float64(outputTokens)/1000.0)*pricing.OutputPricePer1K

	entry := TelemetryEntry{
		Timestamp:    time.Now().UTC().Format(time.RFC3339),
		Provider:     provider,
		Model:        model,
		InputTokens:  inputTokens,
		OutputTokens: outputTokens,
		CostUSD:      cost,
	}

	telemetryPath := filepath.Join(b.workspaceRoot, ".agent", "bus", "telemetry.json")

	b.semaphoresMu.Lock()
	defer b.semaphoresMu.Unlock()

	var telemetry struct {
		TotalCostUSD float64          `json:"total_cost_usd"`
		Calls        []TelemetryEntry `json:"calls,omitempty"`
	}

	data, err := os.ReadFile(telemetryPath)
	if err == nil {
		_ = json.Unmarshal(data, &telemetry)
	}

	telemetry.TotalCostUSD += cost
	telemetry.Calls = append(telemetry.Calls, entry)

	// Trim calls to last 1000 to prevent unbounded growth
	if len(telemetry.Calls) > 1000 {
		telemetry.Calls = telemetry.Calls[len(telemetry.Calls)-1000:]
	}

	writeData, _ := json.MarshalIndent(telemetry, "", "  ")
	_ = os.MkdirAll(filepath.Dir(telemetryPath), 0755)
	_ = os.WriteFile(telemetryPath, writeData, 0644)
}

// isBudgetExceeded checks if the accumulated cost exceeds the watchdog limit
func (b *BrokerServer) isBudgetExceeded(rules *RouterRules) bool {
	telemetryPath := filepath.Join(b.workspaceRoot, ".agent", "bus", "telemetry.json")
	watchdogPath := filepath.Join(b.workspaceRoot, ".agent", "config", "watchdog_rules.json")

	telemetryData, err := os.ReadFile(telemetryPath)
	if err != nil {
		return false
	}
	watchdogData, err := os.ReadFile(watchdogPath)
	if err != nil {
		return false
	}

	var telemetry struct {
		TotalCostUSD float64 `json:"total_cost_usd"`
	}
	var watchdog struct {
		Limits struct {
			CostLimitPerTaskUSD float64 `json:"cost_limit_per_task_usd"`
		} `json:"limits"`
	}

	_ = json.Unmarshal(telemetryData, &telemetry)
	_ = json.Unmarshal(watchdogData, &watchdog)

	limit := watchdog.Limits.CostLimitPerTaskUSD
	if limit <= 0 {
		limit = 2.0
	}

	thresholdRatio := rules.Scoring.Budget.ThresholdRatio
	if thresholdRatio <= 0 {
		thresholdRatio = 0.85
	}

	return telemetry.TotalCostUSD > (limit * thresholdRatio)
}

// agenticToolUse holds a tool_use block from an Anthropic /messages response.
type agenticToolUse struct {
	id    string
	name  string
	input json.RawMessage
}

// formatPerfStats returns a compact stats line appended to the end of a response.
// Example: "166 tok/s (2130 tokens) · score=13 L4 · Qwen3_6-27B-IQ4_XS"
// Returns "" when there is insufficient data (< 0.5 s elapsed or 0 tokens).
func formatPerfStats(outputTokens int, elapsed time.Duration, model, tier string, score int) string {
	if outputTokens <= 0 || elapsed.Seconds() < 0.5 {
		return ""
	}
	s := fmt.Sprintf("%.0f tok/s (%d tokens)", float64(outputTokens)/elapsed.Seconds(), outputTokens)
	if tier != "" || score > 0 {
		s += fmt.Sprintf(" · score=%d %s", score, tier)
	}
	if model != "" {
		s += " · " + model
	}
	return s
}

// agenticStreamKey is the context key used to thread a streaming token callback
// through executePromptLogic into executeAgenticLoop without changing signatures.
// Set by http_server.go for the HTTP streaming path; nil for MCP stdio path.
type agenticStreamKey struct{}

// executeAgenticLoop drives a multi-turn agentic loop using the Anthropic /messages API.
// Jan's native protocol is Anthropic — this avoids spawning a new llamacpp process per
// unique system-prompt prefix (which is what /v1/chat/completions does and causes the
// multi-minute hangs when the model switches context).
//
// GUARANTEE B: on the FIRST iteration tool_choice forces call_agent, so the orchestrator
// ALWAYS delegates instead of answering/fixing things itself. Subsequent iterations use
// "auto" so it can synthesize once sub-agents have responded.
//
// Sub-agent calls (invokeAgent) inside the loop run LOCAL ONLY (withLocalOnly) — they
// never touch the cloud. The semaphore is acquired/released per-iteration.
func (b *BrokerServer) executeAgenticLoop(
	ctx context.Context,
	prompt, systemPrompt, model, provider, baseURL string,
	maxTokens, score int,
	tier string,
) (string, error) {
	if provider != ProviderJan {
		return "", fmt.Errorf("agentic loop requires Jan provider (got %q) — no local L3 model available", provider)
	}

	// Extract the streaming callback injected by http_server.go for the HTTP path.
	var onToken func(string)
	if cb, ok := ctx.Value(agenticStreamKey{}).(func(string)); ok {
		onToken = cb
	}

	const (
		maxIter                 = 10
		maxMessagesHistoryBytes = 20000 // compact history above this JSON-byte threshold
	)

	rules, _ := b.loadRules()
	provLimit := 1 // Jan loads one model at a time
	if rules != nil {
		provLimit = b.getConcurrencyLimit(provider, rules)
	}

	// Cap output tokens — n_ctx is a context-window value, not an output budget.
	if maxTokens <= 0 || maxTokens > 8192 {
		maxTokens = 8192
	}

	// Tool definition in Anthropic tool format.
	callAgentTool := map[string]any{
		"name":        "call_agent",
		"description": b.buildCallAgentDescription(),
		"input_schema": map[string]any{
			"type": "object",
			"properties": map[string]any{
				"agent_name": map[string]any{
					"type":        "string",
					"description": "Exact agent name from the available list.",
				},
				"task": map[string]any{
					"type":        "string",
					"description": "The task or question to send to the agent.",
				},
				"tier": map[string]any{
					"type":        "string",
					"description": "Optional tier override: L1, L2, L3, L4.",
				},
			},
			"required": []string{"agent_name", "task"},
		},
	}

	// Trim system prompt to the first instruction file — same reasoning as before.
	agentSystemPrompt := trimToFirstInstructionFile(systemPrompt)
	fmt.Fprintf(os.Stderr, "[INFO] agentic-loop: system prompt trimmed %d→%d chars\n",
		len(systemPrompt), len(agentSystemPrompt))

	// When opencode expands a slash command (e.g. /brainstorm), it injects the full
	// command template (brainstorm.md content starting with <!-- GENERATED by sync_agents.py -->)
	// into the user message. Strip the template header and frontmatter so the model
	// only sees the user's actual query — otherwise the model echoes the template verbatim.
	userContent := extractUserQuery(prompt)

	// For simple conversational queries, prepend a direct-response hint so the model
	// does not follow the orchestrator delegation protocol and output protocol metadata.
	// The hint is explicit about format (plain markdown, no JSON) because small models
	// tend to generate {"messages":[...]} when they see an orchestrator system prompt.
	if !isComplexEnoughForAgenticLoop(userContent) {
		userContent = "[ИНСТРУКЦИЯ: Это разговорный вопрос. Отвечай кратко обычным текстом или markdown. " +
			"НЕ вызывай агентов. НЕ выводи JSON. НЕ следуй протоколу оркестратора.]\n\n" + userContent
	}

	// Anthropic messages — system prompt goes as top-level field, NOT in messages[].
	messages := []map[string]any{
		{"role": "user", "content": userContent},
	}

	genTimeout := 300 * time.Second
	if rules != nil && rules.Timeouts.GenerationS > 0 {
		genTimeout = time.Duration(rules.Timeouts.GenerationS) * time.Second
	}
	ctx, cancel := context.WithTimeout(ctx, genTimeout)
	defer cancel()

	longClient := b.clientSlow
	if longClient == nil {
		longClient = &http.Client{Timeout: genTimeout}
	}
	var lastText string
	startTime := time.Now()
	var totalOutputTokens int

	for iter := 0; iter < maxIter; iter++ {
		// Compact accumulated history before each request to prevent context overflow.
		messages = b.compactMessagesHistory(ctx, messages, maxMessagesHistoryBytes, baseURL, model)

		release, err := b.acquireSemaphore(ctx, provider, provLimit)
		if err != nil {
			return lastText, fmt.Errorf("%s semaphore iter %d: %w", provider, iter, err)
		}

		// GUARANTEE B — force delegation on the first turn for complex requests.
		// Simple conversational queries (привет, как дела?) skip forced delegation
		// so the model can answer directly in one iteration without calling an agent.
		var toolChoice any = map[string]any{"type": "auto"}
		if iter == 0 && isComplexEnoughForAgenticLoop(prompt) {
			toolChoice = map[string]any{"type": "tool", "name": "call_agent"}
		}

		payload := map[string]any{
			"model":       model,
			"system":      agentSystemPrompt,
			"messages":    messages,
			"tools":       []any{callAgentTool},
			"tool_choice": toolChoice,
			"max_tokens":  maxTokens,
		}

		// Dual path: SSE streaming when onToken callback is present (HTTP path),
		// buffered request otherwise (stdio path).
		var textParts []string
		var toolUses []agenticToolUse
		var iterStopReason string
		var iterOutputTokens int

		if onToken != nil {
			iterResult, iterErr := b.streamAgenticIteration(ctx, payload, baseURL, onToken)
			release()
			if iterErr != nil {
				return lastText, fmt.Errorf("Jan agentic iter %d: %w", iter, iterErr)
			}
			if iterResult.overflow {
				fmt.Fprintf(os.Stderr, "[WARN] agentic-loop iter=%d: context overflow (streaming)\n", iter)
				return lastText, nil
			}
			textParts = iterResult.texts
			toolUses = iterResult.toolUses
			iterStopReason = iterResult.stopReason
			iterOutputTokens = iterResult.outputTokens
			totalOutputTokens += iterOutputTokens
		} else {
			jsonData, err := json.Marshal(payload)
			if err != nil {
				release()
				return lastText, err
			}
			janCtx, janCancel := context.WithTimeout(context.Background(), 300*time.Second)
			req, err := http.NewRequestWithContext(janCtx, "POST",
				fmt.Sprintf("%s/messages", baseURL), bytes.NewReader(jsonData))
			if err != nil {
				janCancel()
				release()
				return lastText, err
			}
			req.Header.Set("Content-Type", "application/json")
			req.Header.Set("anthropic-version", "2023-06-01")
			resp, err := longClient.Do(req)
			janCancel()
			if err != nil {
				release()
				return lastText, fmt.Errorf("Jan agentic iter %d: %w", iter, err)
			}
			respBody, _ := io.ReadAll(resp.Body)
			resp.Body.Close()
			release()

			if resp.StatusCode != http.StatusOK {
				return lastText, fmt.Errorf("Jan HTTP %d: %s", resp.StatusCode, string(respBody))
			}
			if len(respBody) == 0 {
				fmt.Fprintf(os.Stderr, "[WARN] agentic-loop iter=%d: empty response body (context overflow)\n", iter)
				return lastText, nil
			}
			var ar struct {
				Content []struct {
					Type  string          `json:"type"`
					Text  string          `json:"text,omitempty"`
					ID    string          `json:"id,omitempty"`
					Name  string          `json:"name,omitempty"`
					Input json.RawMessage `json:"input,omitempty"`
				} `json:"content"`
				StopReason string `json:"stop_reason"`
				Usage      struct {
					OutputTokens int `json:"output_tokens"`
				} `json:"usage"`
			}
			if err := json.Unmarshal(respBody, &ar); err != nil {
				return lastText, fmt.Errorf("decode Anthropic response: %w", err)
			}
			for _, block := range ar.Content {
				switch block.Type {
				case "text":
					textParts = append(textParts, block.Text)
				case "tool_use":
					toolUses = append(toolUses, agenticToolUse{id: block.ID, name: block.Name, input: block.Input})
				}
			}
			iterStopReason = ar.StopReason
			iterOutputTokens = ar.Usage.OutputTokens
			totalOutputTokens += iterOutputTokens
		}

		if len(textParts) > 0 {
			lastText = stripThinkBlocks(strings.Join(textParts, ""))
		}

		fmt.Fprintf(os.Stderr, "[INFO] agentic-loop iter=%d model=%s stop=%s tool_uses=%d text_len=%d tokens=%d\n",
			iter, model, iterStopReason, len(toolUses), len(lastText), iterOutputTokens)

		// No tool_use → model synthesized a final answer.
		if len(toolUses) == 0 || iterStopReason == "end_turn" {
			stats := formatPerfStats(totalOutputTokens, time.Since(startTime), model, tier, score)
			if onToken != nil {
				// Text already streamed via streamAgenticIteration; append stats only.
				if stats != "" {
					onToken("\n\n" + stats)
				}
				return "", nil
			}
			if stats != "" {
				lastText += "\n\n" + stats
			}
			return lastText, nil
		}

		// Append assistant turn with tool_use blocks (Anthropic format).
		assistantContent := make([]any, 0, len(textParts)+len(toolUses))
		for _, t := range textParts {
			assistantContent = append(assistantContent, map[string]any{"type": "text", "text": t})
		}
		for _, tu := range toolUses {
			var inputObj any
			if err := json.Unmarshal(tu.input, &inputObj); err != nil {
				inputObj = map[string]any{}
			}
			assistantContent = append(assistantContent, map[string]any{
				"type":  "tool_use",
				"id":    tu.id,
				"name":  tu.name,
				"input": inputObj,
			})
		}
		messages = append(messages, map[string]any{
			"role":    "assistant",
			"content": assistantContent,
		})

		// Execute tool calls and append tool_result user turn.
		toolResults := make([]any, 0, len(toolUses))
		for _, tu := range toolUses {
			var resultText string
			if tu.name == "call_agent" {
				var inp map[string]any
				if err := json.Unmarshal(tu.input, &inp); err != nil {
					resultText = fmt.Sprintf("Error parsing call_agent arguments: %v", err)
				} else {
					agentName, _ := inp["agent_name"].(string)
					task, _ := inp["task"].(string)
					tier, _ := inp["tier"].(string)
					fmt.Fprintf(os.Stderr, "[INFO] agentic-loop: call_agent(agent=%q tier=%q task_len=%d)\n",
						agentName, tier, len(task))
					if onToken != nil {
						taskPreview := task
						if len([]rune(taskPreview)) > 80 {
							taskPreview = string([]rune(taskPreview)[:80]) + "…"
						}
						onToken(fmt.Sprintf("\n\n**→ %s** *· %s*\n\n", agentName, taskPreview))
					}
					agentResp, agentErr := b.invokeAgent(ctx, agentName, task, tier, true)
					if agentErr != nil {
						resultText = fmt.Sprintf("Error from %s: %v", agentName, agentErr)
						if onToken != nil {
							onToken(fmt.Sprintf("> ⚠ %s: %v\n\n", agentName, agentErr))
						}
					} else {
						cleanResp, _ := stripSelfReportedIdentityHeader(agentResp.Response)
						resultText = cleanResp
						if onToken != nil && resultText != "" {
							preview := strings.TrimSpace(resultText)
							if len([]rune(preview)) > 600 {
								preview = string([]rune(preview)[:600]) + "…"
							}
							lines := strings.Split(preview, "\n")
							var bq strings.Builder
							for _, l := range lines {
								bq.WriteString("> ")
								bq.WriteString(l)
								bq.WriteString("\n")
							}
							onToken(bq.String() + "\n")
						}
					}
				}
			} else {
				resultText = fmt.Sprintf("Unknown tool %q — not supported in agentic loop.", tu.name)
			}
			toolResults = append(toolResults, map[string]any{
				"type":        "tool_result",
				"tool_use_id": tu.id,
				"content":     resultText,
			})
		}
		// Anthropic requires tool results as a user turn with content array.
		messages = append(messages, map[string]any{
			"role":    "user",
			"content": toolResults,
		})
	}

	fmt.Fprintf(os.Stderr, "[WARN] agentic-loop: exceeded %d iterations — returning last text\n", maxIter)
	stats := formatPerfStats(totalOutputTokens, time.Since(startTime), model, tier, score)
	if onToken != nil {
		if stats != "" {
			onToken("\n\n" + stats)
		}
		return "", nil
	}
	if stats != "" {
		lastText += "\n\n" + stats
	}
	return lastText, nil
}

// ollamaToolCallRecord surfaces one executed tool call for the Council/Arena
// transcript — so handleCallAgent's response can tell "this claim was
// verified" from "this claim was asserted blind" (the distinction this
// entire tool-access feature exists to make possible).
type ollamaToolCallRecord struct {
	Tool   string `json:"tool"`
	Args   any    `json:"args"`
	Result string `json:"result,omitempty"`
	Error  string `json:"error,omitempty"`
}

// executeOllamaToolLoop drives a bounded tool-calling loop against Ollama's
// /api/chat using its OpenAI-compatible function-calling format — a
// parallel, wire-format-distinct counterpart to executeAgenticLoop's
// Jan/Anthropic /messages loop, scoped to local-only, tool-enabled sub-agent
// dispatches (see withToolsEnabled/toolsEnabled). Only read_file/grep
// (tools_readonly.go) are exposed — not call_agent — so a sub-agent persona
// can verify a claim but cannot recursively dispatch other agents.
//
// Empirically confirmed 2026-08-14 against
// oamazonasgabriel/qwen3.6-35b-a3b:q4-24gbGPU (the model in real L4 use for
// this router config): /api/chat honors the "tools" array and returns
// message.tool_calls with `arguments` as a native JSON object (not a
// JSON-encoded string, unlike strict OpenAI) — and correctly consumes a
// role:"tool" follow-up message keyed by tool_call_id to synthesize a final
// answer. This function defensively also accepts a JSON-encoded string for
// `arguments` in case another model quirks differently.
func (b *BrokerServer) executeOllamaToolLoop(
	ctx context.Context,
	prompt, systemPrompt, model, baseURL string,
	maxTokens int,
	rules *RouterRules,
) (string, []ollamaToolCallRecord, error) {
	var rawCfg SubAgentToolsConfig
	if rules != nil {
		rawCfg = rules.SubAgentTools
	}
	budget := newToolBudget(rawCfg) // resolves zero fields internally — do not call .resolved() again here
	cfg := budget.cfg
	toolDefs := buildReadOnlyToolDefs()

	var messages []map[string]any
	if systemPrompt != "" {
		messages = append(messages, map[string]any{"role": "system", "content": systemPrompt})
	}
	messages = append(messages, map[string]any{"role": "user", "content": extractUserQuery(prompt)})

	genTimeout := 300 * time.Second
	if rules != nil && rules.Timeouts.GenerationS > 0 {
		genTimeout = time.Duration(rules.Timeouts.GenerationS) * time.Second
	}
	ctx, cancel := context.WithTimeout(ctx, genTimeout)
	defer cancel()

	client := b.clientSlow
	if client == nil {
		client = &http.Client{Timeout: genTimeout}
	}
	provLimit := b.getConcurrencyLimit(ProviderOllama, rules)

	var log []ollamaToolCallRecord
	var lastErr error

	for iter := 0; iter < cfg.MaxIterations; iter++ {
		opts := map[string]any{"num_ctx": 8192}
		if maxTokens > 0 {
			opts["num_predict"] = maxTokens
		}
		payload := map[string]any{
			"model":    model,
			"messages": messages,
			"tools":    toolDefs,
			"stream":   false,
			"options":  opts,
		}
		jsonData, err := json.Marshal(payload)
		if err != nil {
			return "", log, err
		}

		release, err := b.acquireSemaphore(ctx, ProviderOllama, provLimit)
		if err != nil {
			return "", log, fmt.Errorf("ollama tool loop semaphore iter %d: %w", iter, err)
		}
		req, err := http.NewRequestWithContext(ctx, "POST", baseURL+"/api/chat", bytes.NewReader(jsonData))
		if err != nil {
			release()
			return "", log, err
		}
		req.Header.Set("Content-Type", "application/json")

		resp, err := client.Do(req)
		if err != nil {
			release()
			b.recordProviderFailure(ProviderOllama)
			return "", log, fmt.Errorf("ollama tool loop iter %d: %w", iter, err)
		}
		body, _ := io.ReadAll(resp.Body)
		resp.Body.Close()
		release()

		if resp.StatusCode != http.StatusOK {
			b.recordProviderFailure(ProviderOllama)
			return "", log, fmt.Errorf("ollama tool loop iter %d: HTTP %d: %s", iter, resp.StatusCode, string(body))
		}

		var parsed struct {
			Message struct {
				Role      string `json:"role"`
				Content   string `json:"content"`
				ToolCalls []struct {
					ID       string `json:"id"`
					Function struct {
						Name      string          `json:"name"`
						Arguments json.RawMessage `json:"arguments"`
					} `json:"function"`
				} `json:"tool_calls"`
			} `json:"message"`
			Done bool `json:"done"`
		}
		if err := json.Unmarshal(body, &parsed); err != nil {
			b.recordProviderFailure(ProviderOllama)
			return "", log, fmt.Errorf("decode ollama chat response: %w", err)
		}
		b.recordProviderSuccess(ProviderOllama)

		if len(parsed.Message.ToolCalls) == 0 {
			return stripThinkBlocks(strings.TrimSpace(parsed.Message.Content)), log, nil
		}

		// Append the assistant turn with its tool_calls, then execute each and
		// append a role:"tool" result — format verified empirically above.
		rawToolCalls := make([]map[string]any, 0, len(parsed.Message.ToolCalls))
		for _, tc := range parsed.Message.ToolCalls {
			rawToolCalls = append(rawToolCalls, map[string]any{
				"id":       tc.ID,
				"function": map[string]any{"name": tc.Function.Name, "arguments": tc.Function.Arguments},
			})
		}
		messages = append(messages, map[string]any{
			"role":       "assistant",
			"content":    parsed.Message.Content,
			"tool_calls": rawToolCalls,
		})

		budgetHit := false
		for _, tc := range parsed.Message.ToolCalls {
			var argsObj map[string]any
			if err := json.Unmarshal(tc.Function.Arguments, &argsObj); err != nil {
				// Defensive fallback: some models stringify arguments instead of
				// emitting a native object.
				var asString string
				if jerr := json.Unmarshal(tc.Function.Arguments, &asString); jerr == nil {
					_ = json.Unmarshal([]byte(asString), &argsObj)
				}
			}

			var resultText string
			var callErr error
			if budget.exceeded() {
				callErr = fmt.Errorf("tool-call budget exhausted (%d/%d calls, %d/%d bytes used this dispatch)",
					budget.callsUsed, budget.cfg.MaxToolCalls, budget.bytesUsed, budget.cfg.MaxBytesPerDispatch)
			} else {
				resultText, callErr = b.runReadOnlyTool(ctx, tc.Function.Name, argsObj, budget)
			}

			rec := ollamaToolCallRecord{Tool: tc.Function.Name, Args: argsObj}
			if callErr != nil {
				rec.Error = callErr.Error()
				resultText = "Error: " + callErr.Error()
				lastErr = callErr
			} else {
				summary := resultText
				if len(summary) > 300 {
					summary = truncateAtRuneBoundary(summary, 300) + "…"
				}
				rec.Result = summary
			}
			log = append(log, rec)

			messages = append(messages, map[string]any{
				"role":         "tool",
				"content":      resultText,
				"tool_call_id": tc.ID,
			})

			if budget.exceeded() {
				budgetHit = true
			}
		}

		if budgetHit {
			messages = append(messages, map[string]any{
				"role":    "user",
				"content": "[tool budget exhausted for this dispatch — no further tool calls are available; answer with what you have]",
			})
		}
	}

	fmt.Fprintf(os.Stderr, "[WARN] ollama-tool-loop: exceeded %d iterations without a final answer (last tool error: %v)\n", cfg.MaxIterations, lastErr)
	return "", log, fmt.Errorf("ollama tool loop: exceeded %d iterations without a final answer", cfg.MaxIterations)
}

// isComplexEnoughForAgenticLoop returns true when a prompt requires specialist agent
// delegation — i.e. it is a technical engineering/debugging/analysis task, not a
// simple conversational message. Used to gate the L3 bump and the agentic loop so
// that trivial inputs like "привет" or "напиши стихотворение" are served cheaply by
// an L2 model without spinning up Qwen-27B.
//
// The scoring config only has English keywords; Russian prompts score 5 (base) even
// for complex tasks. This function fills that gap with a bilingual keyword list.
func isComplexEnoughForAgenticLoop(prompt string) bool {
	if len([]rune(prompt)) < 12 {
		return false // pure greetings: "привет", "ok", "да", "нет"
	}
	lower := strings.ToLower(prompt)
	keywords := []string{
		// English technical actions
		"debug", "fix", "implement", "create", "build", "refactor", "test", "check",
		"analyze", "analyse", "review", "investigate", "find", "search", "deploy",
		"optimize", "profile", "trace", "diagnose", "migrate", "integrate",
		// English problem signals
		"error", "fail", "broken", "crash", "bug", "issue", "problem", "exception",
		// Russian technical actions
		"дебаг", "исправ", "создай", "создать", "реализуй", "реализовать",
		"сделай", "сделать", "проверь", "проверить", "найди", "найти",
		"анализ", "отлад", "отладка", "рефактор", "задеплой", "мигрир",
		// Russian problem signals
		"ошибк", "баг", "фич", "проблем", "зависает", "не работает", "сбой",
		// Service/system artifacts (often appear in task descriptions)
		"headroom", "endpoint", "service", "server", "api", "database",
		"файл", "функци", "метод", "класс", "модуль",
	}
	for _, kw := range keywords {
		if strings.Contains(lower, kw) {
			return true
		}
	}
	return false
}

// agenticIterResult holds the outcome of one streaming agentic iteration.
type agenticIterResult struct {
	texts        []string // raw text blocks (may include <think> tags)
	toolUses     []agenticToolUse
	stopReason   string
	inputTokens  int
	outputTokens int
	overflow     bool // true when Jan closed stream without message_stop
}

// streamAgenticIteration makes one SSE streaming request to Jan /messages. Text tokens
// are forwarded in real time via onToken (think-filtered). Structured results (tool_use
// blocks, stop_reason, usage) are returned for the caller to continue the loop.
func (b *BrokerServer) streamAgenticIteration(
	ctx context.Context,
	payload map[string]any,
	baseURL string,
	onToken func(string),
) (*agenticIterResult, error) {
	p := make(map[string]any, len(payload)+1)
	for k, v := range payload {
		p[k] = v
	}
	p["stream"] = true

	jsonData, err := json.Marshal(p)
	if err != nil {
		return nil, err
	}

	req, err := http.NewRequestWithContext(ctx, "POST",
		fmt.Sprintf("%s/messages", baseURL), bytes.NewReader(jsonData))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("anthropic-version", "2023-06-01")

	client := b.clientSlow
	if client == nil {
		client = &http.Client{Timeout: 300 * time.Second}
	}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("Jan HTTP %d: %s", resp.StatusCode, string(body))
	}

	result := &agenticIterResult{}
	filter := &thinkFilter{out: onToken}

	scanner := bufio.NewScanner(resp.Body)
	scanner.Buffer(make([]byte, 64*1024), 64*1024)

	var lastEvent string
	var currentBlockType string
	var currentTool agenticToolUse
	var currentToolInputBuf strings.Builder
	var rawTextBuf strings.Builder

	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if strings.HasPrefix(line, "event: ") {
			lastEvent = strings.TrimPrefix(line, "event: ")
			if lastEvent == "message_stop" {
				break
			}
			continue
		}
		if !strings.HasPrefix(line, "data: ") {
			continue
		}
		raw := []byte(strings.TrimPrefix(line, "data: "))

		switch lastEvent {
		case "message_start":
			var ms struct {
				Message struct {
					Usage struct {
						InputTokens int `json:"input_tokens"`
					} `json:"usage"`
				} `json:"message"`
			}
			if json.Unmarshal(raw, &ms) == nil {
				result.inputTokens = ms.Message.Usage.InputTokens
			}

		case "content_block_start":
			var cbs struct {
				ContentBlock struct {
					Type string `json:"type"`
					ID   string `json:"id"`
					Name string `json:"name"`
				} `json:"content_block"`
			}
			if json.Unmarshal(raw, &cbs) == nil {
				currentBlockType = cbs.ContentBlock.Type
				if currentBlockType == "tool_use" {
					currentTool = agenticToolUse{id: cbs.ContentBlock.ID, name: cbs.ContentBlock.Name}
					currentToolInputBuf.Reset()
				} else if currentBlockType == "text" {
					rawTextBuf.Reset()
				}
			}

		case "content_block_delta":
			var cbd struct {
				Delta struct {
					Type    string `json:"type"`
					Text    string `json:"text,omitempty"`
					Partial string `json:"partial_json,omitempty"`
				} `json:"delta"`
			}
			if json.Unmarshal(raw, &cbd) == nil {
				switch cbd.Delta.Type {
				case "text_delta":
					if cbd.Delta.Text != "" {
						rawTextBuf.WriteString(cbd.Delta.Text)
						filter.feed(cbd.Delta.Text)
					}
				case "input_json_delta":
					if cbd.Delta.Partial != "" {
						currentToolInputBuf.WriteString(cbd.Delta.Partial)
					}
				}
			}

		case "content_block_stop":
			switch currentBlockType {
			case "text":
				if s := rawTextBuf.String(); s != "" {
					result.texts = append(result.texts, s)
				}
			case "tool_use":
				inp := json.RawMessage(currentToolInputBuf.String())
				if len(inp) == 0 {
					inp = json.RawMessage("{}")
				}
				currentTool.input = inp
				result.toolUses = append(result.toolUses, currentTool)
			}
			currentBlockType = ""

		case "message_delta":
			var md struct {
				Delta struct {
					StopReason string `json:"stop_reason"`
				} `json:"delta"`
				Usage struct {
					OutputTokens int `json:"output_tokens"`
				} `json:"usage"`
			}
			if json.Unmarshal(raw, &md) == nil {
				result.stopReason = md.Delta.StopReason
				result.outputTokens = md.Usage.OutputTokens
			}
		}
	}
	filter.flush()
	if err := scanner.Err(); err != nil {
		return nil, err
	}

	// Jan sometimes closes the stream without message_stop when context overflows.
	if result.stopReason == "" && len(result.toolUses) == 0 {
		result.overflow = true
	}
	return result, nil
}

// compactMessagesHistory replaces accumulated message pairs with an LLM-generated
// summary when the total history exceeds maxBytes. Preserves messages[0] (the
// original user request). Uses the fastest available Jan L1 model for the
// summarisation call; falls back to the orchestrator model if L1 is not loaded.
// If the summarisation HTTP call fails entirely, the original messages are returned
// unchanged — context overflow is then handled by the empty-body guard.
func (b *BrokerServer) compactMessagesHistory(
	ctx context.Context,
	messages []map[string]any,
	maxBytes int,
	baseURL, fallbackModel string,
) []map[string]any {
	if len(messages) < 3 {
		return messages
	}
	data, _ := json.Marshal(messages)
	if len(data) <= maxBytes {
		return messages
	}

	compactModel := b.findL1ModelForJan(ctx, baseURL)
	if compactModel == "" {
		compactModel = fallbackModel // L3 orchestrator — already warm in Jan
	}

	// Render old pairs as readable text for the summariser.
	var sb strings.Builder
	sb.WriteString("Summarize the following LLM tool interactions. Preserve all key findings, errors, filenames, and recommendations. Max 400 words.\n\n")
	for i, m := range messages[1:] {
		role, _ := m["role"].(string)
		fmt.Fprintf(&sb, "[%d/%s]\n", i+1, role)
		contentJSON, _ := json.Marshal(m["content"])
		sb.Write(contentJSON)
		sb.WriteString("\n")
	}

	payload := map[string]any{
		"model":  compactModel,
		"system": "You are a concise summarizer. Given tool interaction logs, produce a brief summary of key findings.",
		"messages": []map[string]any{
			{"role": "user", "content": sb.String()},
		},
		"max_tokens": 600,
	}
	jsonData, _ := json.Marshal(payload)

	compactCtx, cancel := context.WithTimeout(ctx, 60*time.Second)
	defer cancel()
	req, err := http.NewRequestWithContext(compactCtx, "POST",
		fmt.Sprintf("%s/messages", baseURL), bytes.NewReader(jsonData))
	if err != nil {
		fmt.Fprintf(os.Stderr, "[WARN] compact: build request: %v\n", err)
		return messages
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("anthropic-version", "2023-06-01")

	client := b.clientFast
	if client == nil {
		client = &http.Client{Timeout: 60 * time.Second}
	}
	resp, err := client.Do(req)
	if err != nil {
		fmt.Fprintf(os.Stderr, "[WARN] compact: HTTP: %v\n", err)
		return messages
	}
	body, _ := io.ReadAll(resp.Body)
	resp.Body.Close()

	if resp.StatusCode != http.StatusOK || len(body) == 0 {
		fmt.Fprintf(os.Stderr, "[WARN] compact: bad response status=%d body_len=%d\n", resp.StatusCode, len(body))
		return messages
	}

	var ar struct {
		Content []struct {
			Type string `json:"type"`
			Text string `json:"text"`
		} `json:"content"`
	}
	if err := json.Unmarshal(body, &ar); err != nil {
		fmt.Fprintf(os.Stderr, "[WARN] compact: parse: %v\n", err)
		return messages
	}
	var summary string
	for _, c := range ar.Content {
		if c.Type == "text" {
			summary = c.Text
			break
		}
	}
	if summary == "" {
		fmt.Fprintf(os.Stderr, "[WARN] compact: empty summary\n")
		return messages
	}

	fmt.Fprintf(os.Stderr, "[INFO] compact: %d messages → summary (%d chars) via model=%s\n",
		len(messages), len(summary), compactModel)
	return []map[string]any{
		messages[0],
		{"role": "user", "content": "[Summary of previous tool interactions]\n" + summary},
	}
}

// findL1ModelForJan fetches Jan's loaded model list and returns the first one
// that matches an L1-tier config entry. Returns "" if none is found.
func (b *BrokerServer) findL1ModelForJan(ctx context.Context, baseURL string) string {
	rules, _ := b.loadRules()
	if rules == nil {
		return ""
	}
	reqCtx, cancel := context.WithTimeout(ctx, 2*time.Second)
	defer cancel()
	pulledList, err := b.fetchOpenAICompatibleModels(reqCtx, baseURL)
	if err != nil || len(pulledList) == 0 {
		return ""
	}
	for _, name := range pulledList {
		if isTierCompatibleWith(b.getModelTier(name, rules), "L1") {
			return name
		}
	}
	return ""
}

// isOrchestratorContext returns true when the system prompt is an orchestrator
// agent context — either a stripped agent body ("You are the master orchestrator…")
// or a raw markdown file that still has YAML frontmatter ("name: orchestrator").
//
// Two signals are required simultaneously:
//  1. ROLE DECLARATION — "you are"/"your role" in the first 1500 chars (covers body)
//     OR "name: orchestrator" in the YAML frontmatter (covers raw .md files as sent
//     by opencode which concatenates instruction files verbatim including frontmatter).
//  2. DOMAIN WORD — one of the orchestration-role words confirms it's not a stray match.
//     "delegates_to" is in the orchestrator.md YAML frontmatter — always present.
//
// NOTE: "call_agent" was previously required as Signal 2 but none of the opencode
// instruction files contain it, making isOrchestratorContext always return false.
// The two remaining signals are specific enough: "name: orchestrator" + "delegates_to".
func isOrchestratorContext(systemPrompt string) bool {
	if len(systemPrompt) < 200 {
		return false
	}

	// Signal 1: role declaration.
	// Extend scan to 1500 chars so YAML frontmatter is included.
	// orchestrator.md frontmatter contains "name: orchestrator" which is unique enough.
	scanLen := 1500
	if len(systemPrompt) < scanLen {
		scanLen = len(systemPrompt)
	}
	opening := strings.ToLower(systemPrompt[:scanLen])
	hasRoleDecl := strings.Contains(opening, "you are") ||
		strings.Contains(opening, "your role") ||
		strings.Contains(opening, "name: orchestrator")
	if !hasRoleDecl {
		return false
	}

	// Signal 2: orchestration-role word confirms this isn't an accidental match.
	lower := strings.ToLower(systemPrompt)
	for _, kw := range []string{"orchestrator", "multi-agent", "sub-agent", "subagent", "delegates_to"} {
		if strings.Contains(lower, kw) {
			return true
		}
	}
	return false
}

// trimToFirstInstructionFile extracts only the first instruction file from a
// concatenated system prompt. opencode concatenates all instruction files in
// opencode.json#instructions[] into a single string; each file starts with the
// "<!-- GENERATED" comment header inserted by sync_agents.py. Sending all files
// to a local 32K-context model fills the context completely — the orchestrator
// only needs its own file (orchestrator.md) to route tasks via call_agent.
// extractUserQuery strips the opencode slash-command template preamble from a prompt.
// When opencode expands /brainstorm (or any slash command), it prepends the full
// command template (brainstorm.md, starting with <!-- GENERATED by sync_agents.py -->)
// to the user's actual query. The template structure is:
//
//	<!-- GENERATED ... -->
//	---
//	description: ...
//	agent: orchestrator
//	---
//	# /brainstorm - Title
//
//	<user query here>
//
//	---
//	## Purpose ...
//
// Returns the extracted user query, or the original prompt if no template header found.
func extractUserQuery(prompt string) string {
	if !strings.HasPrefix(strings.TrimSpace(prompt), "<!-- GENERATED") {
		return prompt
	}
	lines := strings.Split(prompt, "\n")
	dashCount := 0
	commandHeaderPassed := false
	inQuery := false
	var queryLines []string
	for _, line := range lines {
		t := strings.TrimSpace(line)
		if t == "---" {
			dashCount++
			if inQuery {
				break // first --- after the header ends the query section
			}
			continue
		}
		// After second --- (end of YAML frontmatter), look for # /command header.
		if dashCount >= 2 && !commandHeaderPassed && strings.HasPrefix(t, "# /") {
			commandHeaderPassed = true
			continue
		}
		if commandHeaderPassed {
			inQuery = true
			queryLines = append(queryLines, line)
		}
	}
	result := strings.TrimSpace(strings.Join(queryLines, "\n"))
	if result == "" {
		return prompt
	}
	fmt.Fprintf(os.Stderr, "[INFO] extractUserQuery: stripped command template, extracted %d chars from %d\n",
		len(result), len(prompt))
	return result
}

func trimToFirstInstructionFile(systemPrompt string) string {
	const marker = "<!-- GENERATED"
	// Find the second occurrence of the marker (start of the second file).
	first := strings.Index(systemPrompt, marker)
	if first >= 0 {
		second := strings.Index(systemPrompt[first+len(marker):], marker)
		if second >= 0 {
			end := first + len(marker) + second
			return strings.TrimRight(systemPrompt[:end], "\n\r\t ")
		}
	}

	// Fallback for OpenCode concatenated instructions where subsequent files
	// do not start with the generated marker but start with "trigger: always_on".
	if idx := strings.Index(systemPrompt, "trigger: always_on"); idx >= 0 {
		if lastDash := strings.LastIndex(systemPrompt[:idx], "---"); lastDash >= 0 {
			return strings.TrimRight(systemPrompt[:lastDash], "\n\r\t ")
		}
	}

	return systemPrompt
}

// janContextError holds parsed fields from Jan's exceed_context_size_error response.
type janContextError struct {
	NCtx          int
	NPromptTokens int
}

// parseJanContextError returns non-nil if respBody is a Jan exceed_context_size_error.
func parseJanContextError(respBody []byte) *janContextError {
	var errResp struct {
		Error struct {
			Type          string `json:"type"`
			NCtx          int    `json:"n_ctx"`
			NPromptTokens int    `json:"n_prompt_tokens"`
		} `json:"error"`
	}
	if json.Unmarshal(respBody, &errResp) == nil && errResp.Error.Type == "exceed_context_size_error" {
		return &janContextError{NCtx: errResp.Error.NCtx, NPromptTokens: errResp.Error.NPromptTokens}
	}
	return nil
}

// trimSystemPromptByTokens removes `excessTokens` worth of text from the end of the
// system prompt, cutting at a newline boundary to preserve coherence.
func trimSystemPromptByTokens(systemPrompt string, excessTokens int) string {
	const charsPerToken = 4
	removeChars := excessTokens * charsPerToken
	runes := []rune(systemPrompt)
	if removeChars >= len(runes) {
		return ""
	}
	keep := len(runes) - removeChars
	truncated := string(runes[:keep])
	if idx := strings.LastIndex(truncated, "\n"); idx > keep/2 {
		truncated = truncated[:idx]
	}
	return truncated + "\n[...system prompt truncated to fit Jan context window...]"
}

// fixMojibake repairs UTF-8 text that was misread as Latin-1 (e.g. WSL clipboard copy-paste).
// Pattern: "с" (U+0441, UTF-8: 0xD1 0x81) becomes "Ñ" (U+00D1) + invisible 0x81 control char.
// Fix: if every rune fits in one byte AND those bytes form valid UTF-8 with fewer runes → repair.
func fixMojibake(s string) string {
	runes := []rune(s)
	bs := make([]byte, 0, len(runes))
	for _, r := range runes {
		if r > 0xFF {
			return s // already contains non-Latin-1 chars — not mojibake
		}
		bs = append(bs, byte(r))
	}
	if utf8.Valid(bs) && utf8.RuneCountInString(string(bs)) < len(runes) {
		return string(bs)
	}
	return s
}

// Pre-processing Middleware (Whitespace cleanup + encoding repair)
func (b *BrokerServer) runPreprocessMiddleware(prompt string) string {
	prompt = strings.TrimSpace(prompt)
	prompt = fixMojibake(prompt)
	return prompt
}

// Caching Helpers
func (b *BrokerServer) getCacheKey(prompt, systemPrompt, model string) string {
	h := sha256.New()
	h.Write([]byte(prompt + "\n" + systemPrompt + "\n" + model))
	return hex.EncodeToString(h.Sum(nil))
}

func (b *BrokerServer) checkCache(key string) (string, bool) {
	cachePath := filepath.Join(b.workspaceRoot, ".agent", "tmp", "llm_cache", key+".txt")
	data, err := os.ReadFile(cachePath)
	if err != nil {
		return "", false
	}
	return string(data), true
}

func (b *BrokerServer) saveCache(key string, response string) {
	cacheDir := filepath.Join(b.workspaceRoot, ".agent", "tmp", "llm_cache")
	_ = os.MkdirAll(cacheDir, 0755)

	cachePath := filepath.Join(cacheDir, key+".txt")
	_ = os.WriteFile(cachePath, []byte(response), 0644)
}

func (b *BrokerServer) getStringArg(args interface{}, name string) string {
	if m, ok := args.(map[string]interface{}); ok {
		if val, ok := m[name].(string); ok {
			return val
		}
	}
	return ""
}

// getBoolArgDefault reads a bool argument that may arrive as either a native
// bool or a "true"/"false" string (mirrors the "stream" parsing pattern in
// handleExecutePrompt), returning def when the argument is absent.
func (b *BrokerServer) getBoolArgDefault(args interface{}, name string, def bool) bool {
	m, ok := args.(map[string]interface{})
	if !ok {
		return def
	}
	v, ok := m[name]
	if !ok {
		return def
	}
	switch val := v.(type) {
	case bool:
		return val
	case string:
		if val == "" {
			return def
		}
		return val == "true"
	default:
		return def
	}
}

func (b *BrokerServer) getConcurrencyLimit(provider string, rules *RouterRules) int {
	if rules != nil && rules.Concurrency != nil {
		if limit, ok := rules.Concurrency[provider]; ok && limit > 0 {
			return limit
		}
		if limit, ok := rules.Concurrency["default"]; ok && limit > 0 {
			return limit
		}
	}
	return 4 // default fallback
}

func (b *BrokerServer) acquireSemaphore(ctx context.Context, provider string, limit int) (func(), error) {
	b.semaphoresMu.Lock()
	if b.semaphores == nil {
		b.semaphores = make(map[string]chan struct{})
	}
	sem, ok := b.semaphores[provider]
	if !ok {
		sem = make(chan struct{}, limit)
		b.semaphores[provider] = sem
	}
	b.semaphoresMu.Unlock()

	select {
	case sem <- struct{}{}:
		return func() {
			<-sem
		}, nil
	case <-ctx.Done():
		return nil, ctx.Err()
	}
}

type SemanticCacheEntry struct {
	Prompt    string    `json:"prompt"`
	Response  string    `json:"response"`
	Model     string    `json:"model"`
	Embedding []float64 `json:"embedding"`
}

func (b *BrokerServer) loadSemanticCache() ([]SemanticCacheEntry, error) {
	cacheDir := filepath.Join(b.workspaceRoot, ".agent", "tmp", "semantic_cache")
	files, err := os.ReadDir(cacheDir)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}

	var entries []SemanticCacheEntry
	for _, f := range files {
		if !f.IsDir() && strings.HasSuffix(f.Name(), ".json") {
			data, err := os.ReadFile(filepath.Join(cacheDir, f.Name()))
			if err == nil {
				var entry SemanticCacheEntry
				if err := json.Unmarshal(data, &entry); err == nil {
					entries = append(entries, entry)
				}
			}
		}
	}
	return entries, nil
}

func (b *BrokerServer) saveSemanticCacheEntry(key string, entry SemanticCacheEntry) {
	cacheDir := filepath.Join(b.workspaceRoot, ".agent", "tmp", "semantic_cache")
	_ = os.MkdirAll(cacheDir, 0755)

	data, err := json.MarshalIndent(entry, "", "  ")
	if err == nil {
		_ = os.WriteFile(filepath.Join(cacheDir, key+".json"), data, 0644)
	}
}

func cosineSimilarity(a, b []float64) float64 {
	if len(a) != len(b) || len(a) == 0 {
		return 0.0
	}
	var dotProduct, normA, normB float64
	for i := range a {
		dotProduct += a[i] * b[i]
		normA += a[i] * a[i]
		normB += b[i] * b[i]
	}
	if normA == 0.0 || normB == 0.0 {
		return 0.0
	}
	return dotProduct / (math.Sqrt(normA) * math.Sqrt(normB))
}

func (b *BrokerServer) fetchEmbedding(ctx context.Context, provider string, baseURL string, model string, prompt string) ([]float64, error) {
	cacheTimeout := 5 * time.Second
	if rules, err := b.loadRules(); err == nil && rules.Timeouts.SemanticCacheS > 0 {
		cacheTimeout = time.Duration(rules.Timeouts.SemanticCacheS) * time.Second
	}
	ctx, cancel := context.WithTimeout(ctx, cacheTimeout)
	defer cancel()

	client := b.clientFast
	if client == nil {
		client = &http.Client{Timeout: cacheTimeout}
	}

	if provider == ProviderOllama || strings.Contains(baseURL, OllamaDefaultPortStr) {
		url := fmt.Sprintf("%s/api/embeddings", baseURL)
		payload := map[string]interface{}{
			"model":  model,
			"prompt": prompt,
		}
		jsonData, err := json.Marshal(payload)
		if err != nil {
			return nil, err
		}

		req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewBuffer(jsonData))
		if err != nil {
			return nil, err
		}
		req.Header.Set("Content-Type", "application/json")

		resp, err := client.Do(req)
		if err != nil {
			return nil, err
		}
		defer resp.Body.Close()

		if resp.StatusCode != http.StatusOK {
			return nil, fmt.Errorf("status %d", resp.StatusCode)
		}

		var ollamaResp struct {
			Embedding []float64 `json:"embedding"`
		}
		if err := json.NewDecoder(resp.Body).Decode(&ollamaResp); err != nil {
			return nil, err
		}
		return ollamaResp.Embedding, nil
	}

	url := fmt.Sprintf("%s/v1/embeddings", baseURL)
	payload := map[string]interface{}{
		"model": model,
		"input": prompt,
	}
	jsonData, err := json.Marshal(payload)
	if err != nil {
		return nil, err
	}

	req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("status %d", resp.StatusCode)
	}

	var openaiResp struct {
		Data []struct {
			Embedding []float64 `json:"embedding"`
		} `json:"data"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&openaiResp); err != nil {
		return nil, err
	}

	if len(openaiResp.Data) > 0 {
		return openaiResp.Data[0].Embedding, nil
	}

	return nil, fmt.Errorf("empty embeddings response data")
}

// recordProviderFailure увеличивает счётчик ошибок и переводит в Open при достижении порога.
func (b *BrokerServer) recordProviderFailure(provider string) {
	b.healthCacheMu.Lock()
	defer b.healthCacheMu.Unlock()

	if b.healthCache == nil {
		b.healthCache = make(map[string]BackendHealth)
	}

	h := b.healthCache[provider]
	h.ConsecutiveFailures++
	threshold := CBDefaultFailureThreshold
	// Переопределение из конфига (если есть)
	if rules, err := b.loadRules(); err == nil && rules.CircuitBreaker != nil {
		if rules.CircuitBreaker.FailureThreshold > 0 {
			threshold = rules.CircuitBreaker.FailureThreshold
		}
	}
	if h.ConsecutiveFailures >= threshold || h.CircuitState == CircuitHalfOpen {
		h.CircuitState = CircuitOpen
		h.LastFailureTime = time.Now()
		fmt.Fprintf(os.Stderr, "[CIRCUIT] %s → OPEN (ошибок=%d)\n", provider, h.ConsecutiveFailures)
	}
	b.healthCache[provider] = h
}

// recordProviderSuccess сбрасывает circuit в Closed.
func (b *BrokerServer) recordProviderSuccess(provider string) {
	b.healthCacheMu.Lock()
	defer b.healthCacheMu.Unlock()

	if b.healthCache == nil {
		b.healthCache = make(map[string]BackendHealth)
	}

	h := b.healthCache[provider]
	if h.CircuitState != CircuitClosed {
		fmt.Fprintf(os.Stderr, "[CIRCUIT] %s → CLOSED (восстановлен)\n", provider)
	}
	h.ConsecutiveFailures = 0
	h.CircuitState = CircuitClosed
	b.healthCache[provider] = h
}

// isCircuitOpen возвращает true если провайдер следует пропустить.
// Обрабатывает переход Open → HalfOpen после recovery timeout.
func (b *BrokerServer) isCircuitOpen(provider string) bool {
	b.healthCacheMu.Lock()
	defer b.healthCacheMu.Unlock()

	if b.healthCache == nil {
		b.healthCache = make(map[string]BackendHealth)
	}

	h := b.healthCache[provider]

	recoveryTimeout := time.Duration(CBDefaultRecoveryTimeoutS) * time.Second
	// Переопределение из конфига
	rules, err := b.loadRules()
	if err == nil && rules.CircuitBreaker != nil {
		if rules.CircuitBreaker.RecoveryTimeoutS > 0 {
			recoveryTimeout = time.Duration(rules.CircuitBreaker.RecoveryTimeoutS) * time.Second
		}
	}

	switch h.CircuitState {
	case CircuitOpen:
		if time.Since(h.LastFailureTime) > recoveryTimeout {
			h.CircuitState = CircuitHalfOpen
			b.healthCache[provider] = h
			fmt.Fprintf(os.Stderr, "[CIRCUIT] %s → HALF-OPEN (пробный запрос разрешён)\n", provider)
			return false // разрешаем одну проверку
		}
		return true // пропускаем
	case CircuitHalfOpen:
		return false // разрешаем пробный запрос
	default:
		// Мягкий контур: проверка на основе EMA
		softThreshold := CBDefaultSoftEMAThreshold
		if err == nil && rules.CircuitBreaker != nil {
			if rules.CircuitBreaker.SoftEMAThreshold > 0 {
				softThreshold = rules.CircuitBreaker.SoftEMAThreshold
			}
		}
		if h.TotalTokens >= EMAMinTokensForReliability && h.EMAMsPerToken > softThreshold {
			fmt.Fprintf(os.Stderr, "[CIRCUIT] %s мягкое открытие: EMA=%.0fмс/ток > порог %.0f\n",
				provider, h.EMAMsPerToken, softThreshold)
			return true
		}
		return false
	}
}

// RuleLoaderPort defines the contract for loading agent rules.
type RuleLoaderPort interface {
	LoadRules(systemPrompt, userPrompt, tier string) (string, error)
}

// FileRuleLoaderAdapter implements RuleLoaderPort by reading rules from local filesystem.
type FileRuleLoaderAdapter struct {
	workspaceRoot string
}

func NewFileRuleLoaderAdapter(workspaceRoot string) *FileRuleLoaderAdapter {
	return &FileRuleLoaderAdapter{workspaceRoot: workspaceRoot}
}

func (a *FileRuleLoaderAdapter) LoadRules(systemPrompt, userPrompt, tier string) (string, error) {
	rulesDir := filepath.Join(a.workspaceRoot, ".agent", "rules", "gemini")

	// Core rules (always injected)
	filesToLoad := []string{
		"00_protocol.md",
		"04_tier0_universal.md",
		"10_rtk.md",
	}

	// Code rules
	promptLower := strings.ToLower(userPrompt) + " " + strings.ToLower(systemPrompt)
	isCodeTask := tier == "L2" || tier == "L3" || tier == "L4" ||
		strings.Contains(promptLower, "code") ||
		strings.Contains(promptLower, "test") ||
		strings.Contains(promptLower, "implement") ||
		strings.Contains(promptLower, "refactor") ||
		strings.Contains(promptLower, "go") ||
		strings.Contains(promptLower, "python") ||
		strings.Contains(promptLower, "rust") ||
		strings.Contains(promptLower, "bug") ||
		strings.Contains(promptLower, "fix")

	if isCodeTask {
		filesToLoad = append(filesToLoad, "05_tier1_code.md")
	}

	// Go specific
	if strings.Contains(promptLower, "go") || strings.Contains(promptLower, "golang") {
		filesToLoad = append(filesToLoad, "09_go_dependency_management.md")
	}

	// Design / UI
	isDesignTask := strings.Contains(promptLower, "ui") ||
		strings.Contains(promptLower, "design") ||
		strings.Contains(promptLower, "css") ||
		strings.Contains(promptLower, "html") ||
		strings.Contains(promptLower, "frontend") ||
		strings.Contains(promptLower, "dashboard") ||
		strings.Contains(promptLower, "style")
	if isDesignTask {
		filesToLoad = append(filesToLoad, "06_tier2_design.md")
	}

	// Gateway (Tier L4 only)
	if tier == "L4" {
		filesToLoad = append(filesToLoad, "03_gateway.md")
	}

	var rulesBuilder strings.Builder
	rulesBuilder.WriteString("<!-- DYNAMICALLY INJECTED RULES -->\n")

	for _, fname := range filesToLoad {
		fpath := filepath.Join(rulesDir, fname)
		content, err := os.ReadFile(fpath)
		if err != nil {
			fmt.Fprintf(os.Stderr, "[WARN] FileRuleLoaderAdapter: failed to read rule file %s: %v\n", fname, err)
			continue
		}

		// Schema validation step (verify trigger: always_on or trigger: paperclip_infra_only)
		if !strings.Contains(string(content), "trigger: always_on") && !strings.Contains(string(content), "trigger: paperclip_infra_only") {
			fmt.Fprintf(os.Stderr, "[WARN] FileRuleLoaderAdapter: rule file %s lacks expected trigger schema\n", fname)
		}

		rulesBuilder.Write(content)
		rulesBuilder.WriteString("\n\n---\n\n")
	}

	cleanSystemPrompt := stripOldRules(systemPrompt)

	// Combine dynamically loaded rules with the original cleaned system prompt
	finalPrompt := rulesBuilder.String() + cleanSystemPrompt
	return finalPrompt, nil
}

func stripOldRules(prompt string) string {
	lines := strings.Split(prompt, "\n")
	var result []string
	skipping := false

	for _, line := range lines {
		trimmed := strings.TrimSpace(line)

		// If we encounter a major rules header, start skipping
		if strings.HasPrefix(trimmed, "## TIER 0: UNIVERSAL RULES") ||
			strings.HasPrefix(trimmed, "## TIER 1: CODE RULES") ||
			strings.HasPrefix(trimmed, "## TIER 2: DESIGN RULES") ||
			strings.HasPrefix(trimmed, "## TIER 3: PAPERCLIP AGENTIC PROTOCOLS") ||
			strings.HasPrefix(trimmed, "# 🛡️ QuoteSystemX Go Dependency Management") ||
			strings.HasPrefix(trimmed, "# RTK - Rust Token Killer") ||
			strings.HasPrefix(trimmed, "## 🤖 INTELLIGENT AGENT ROUTING") ||
			strings.HasPrefix(trimmed, "## 📥 REQUEST CLASSIFIER") ||
			strings.HasPrefix(trimmed, "# Output Gateway Protocol") ||
			strings.HasPrefix(trimmed, "## 📤 OUTPUT GATEWAY") ||
			strings.HasPrefix(trimmed, "<!-- \n🔴 ATTENTION: THIS FILE IS AUTO-GENERATED") ||
			strings.HasPrefix(trimmed, "🔴 ATTENTION: THIS FILE IS AUTO-GENERATED") {
			skipping = true
			continue
		}

		if skipping {
			if strings.Contains(trimmed, "Always use rtk <cmd> instead of raw commands.") ||
				strings.Contains(trimmed, "Always use `rtk <cmd>` instead of raw commands.") ||
				trimmed == "-->" {
				skipping = false
				continue
			}
			continue
		}

		result = append(result, line)
	}

	return strings.Join(result, "\n")
}
