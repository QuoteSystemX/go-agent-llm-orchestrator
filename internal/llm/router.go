package llm

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"

	"go-agent-llm-orchestrator/internal/db"
	"go-agent-llm-orchestrator/internal/monitor"
)

type Router struct {
	db             *db.DB
	LocalEndpoint  string
	RemoteEndpoint string
	RemoteAPIKey   string
	// inferMu gates access to the local Ollama instance.
	// Embeddings hold RLock; inference holds Lock so it waits for the
	// current embedding chunk to finish before taking over.
	inferMu sync.RWMutex

	// modelCtxMu protects modelCtxCache across goroutines.
	modelCtxMu    sync.Mutex
	modelCtxCache map[string]int // model name → detected context window
}

// InferenceMutex returns the Ollama priority gate so the embedding pipeline
// can register itself as a reader.
func (r *Router) InferenceMutex() *sync.RWMutex { return &r.inferMu }

func NewRouter(database *db.DB) *Router {
	return &Router{
		db:             database,
		LocalEndpoint:  os.Getenv("LLM_LOCAL_ENDPOINT"),
		RemoteEndpoint: os.Getenv("LLM_REMOTE_ENDPOINT"),
		RemoteAPIKey:   os.Getenv("LLM_REMOTE_API_KEY"),
		modelCtxCache:  make(map[string]int),
	}
}

// GetModelContextWindow returns the practical context window for the current local
// model by querying Ollama /api/show. Priority order:
//  1. parameters.num_ctx  — explicit value set in the model's Modelfile
//  2. model_info.<arch>.rope.scaling.original_context_length  — training sweet-spot
//     for RoPE-scaled models (e.g. qwen2.5-coder:1.5b=32768, llama3.1=128000)
//  3. model_info.<arch>.context_length  — capped at 32768 to avoid OOM on small machines
//  4. llm_local_context_window DB setting  — last-resort fallback
//
// Results are cached per model name so /api/show is only called once per unique model.
func (r *Router) GetModelContextWindow() int {
	model := r.getLocalModel()

	r.modelCtxMu.Lock()
	if n, ok := r.modelCtxCache[model]; ok {
		r.modelCtxMu.Unlock()
		return n
	}
	r.modelCtxMu.Unlock()

	n := r.probeModelContext(model)

	r.modelCtxMu.Lock()
	r.modelCtxCache[model] = n
	r.modelCtxMu.Unlock()

	return n
}

// InvalidateModelContextCache clears the cached context window so the next call to
// GetModelContextWindow re-queries Ollama. Call this after changing the local model.
func (r *Router) InvalidateModelContextCache() {
	r.modelCtxMu.Lock()
	r.modelCtxCache = make(map[string]int)
	r.modelCtxMu.Unlock()
}

func (r *Router) probeModelContext(model string) int {
	fallback := r.getLocalContextWindow()

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	// Ollama native API lives at /api/, not /v1/
	baseURL := strings.TrimSuffix(strings.TrimSuffix(r.LocalEndpoint, "/v1"), "/")
	payload, _ := json.Marshal(map[string]string{"name": model})
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, baseURL+"/api/show", bytes.NewReader(payload))
	if err != nil {
		return fallback
	}
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Do(req)
	if err != nil || resp.StatusCode != http.StatusOK {
		if resp != nil {
			resp.Body.Close()
		}
		log.Printf("LLM Router: /api/show probe failed for %q, using DB fallback %d: %v", model, fallback, err)
		return fallback
	}
	defer resp.Body.Close()

	var show struct {
		Parameters string                 `json:"parameters"`
		ModelInfo  map[string]interface{} `json:"model_info"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&show); err != nil {
		return fallback
	}

	// 1. Explicit num_ctx in Modelfile parameters (highest authority)
	for _, line := range strings.Split(show.Parameters, "\n") {
		fields := strings.Fields(line)
		if len(fields) == 2 && fields[0] == "num_ctx" {
			var n int
			if count, _ := fmt.Sscanf(fields[1], "%d", &n); count == 1 && n > 0 {
				log.Printf("LLM Router: model %q context window from Modelfile: %d", model, n)
				return n
			}
		}
	}

	// 2. RoPE scaling original context — practical sweet-spot before the extension
	for key, val := range show.ModelInfo {
		if strings.HasSuffix(key, ".rope.scaling.original_context_length") {
			if n, ok := val.(float64); ok && n > 0 {
				log.Printf("LLM Router: model %q context window from rope.scaling: %d", model, int(n))
				return int(n)
			}
		}
	}

	// 3. Architecture max context — cap to avoid OOM on memory-constrained nodes
	const practicalMaxCtx = 32768
	for key, val := range show.ModelInfo {
		if strings.HasSuffix(key, ".context_length") {
			if n, ok := val.(float64); ok && n > 0 {
				detected := int(n)
				if detected > practicalMaxCtx {
					detected = practicalMaxCtx
				}
				log.Printf("LLM Router: model %q context window from context_length (capped): %d", model, detected)
				return detected
			}
		}
	}

	return fallback
}

func (r *Router) getModel(key, defaultValue string) string {
	var val string
	err := r.db.QueryRow("SELECT value FROM settings WHERE key = ?", key).Scan(&val)
	if err != nil || val == "" {
		return defaultValue
	}
	return val
}

func (r *Router) getLocalModel() string {
	val, source := r.getModelWithSource("llm_local_model", os.Getenv("LLM_LOCAL_MODEL"))
	if val == "" {
		val = "phi3:mini"
		source = "hardcoded-fallback"
	}
	log.Printf("LLM Router: selected local model %q (source: %s)", val, source)
	return val
}

func (r *Router) getModelWithSource(key, defaultValue string) (string, string) {
	if r.db == nil {
		return defaultValue, "env-no-db"
	}
	
	// Try DB
	val := r.db.GetSetting(key, "")
	if val != "" {
		// Check if it was from Env via GetSetting's internal fallback
		if val == os.Getenv(strings.ToUpper(key)) {
			return val, "env"
		}
		return val, "database"
	}

	return defaultValue, "default"
}

func (r *Router) getRemoteModel() string {
	return r.getModel("llm_remote_model", os.Getenv("LLM_REMOTE_MODEL"))
}

func (r *Router) getLocalContextWindow() int {
	valStr := r.getModel("llm_local_context_window", "4096")
	var val int
	fmt.Sscanf(valStr, "%d", &val)
	return val
}

func (r *Router) getLocalTemperature() float64 {
	valStr := r.getModel("llm_local_temperature", "0.7")
	var val float64
	fmt.Sscanf(valStr, "%f", &val)
	return val
}

func (r *Router) getLocalTimeout() time.Duration {
	valStr := r.getModel("llm_local_timeout", "600")
	var val int
	fmt.Sscanf(valStr, "%d", &val)
	if val <= 0 {
		val = 300
	}
	return time.Duration(val) * time.Second
}

// getDTOTimeout returns the timeout for DTO (analysis) LLM calls.
// Configurable via llm_dto_timeout in DB (seconds). Default matches llm_local_timeout (600s).
func (r *Router) getDTOTimeout() time.Duration {
	valStr := r.getModel("llm_dto_timeout", "600")
	var val int
	fmt.Sscanf(valStr, "%d", &val)
	if val <= 0 {
		val = 600
	}
	return time.Duration(val) * time.Second
}

func (r *Router) getLocalRetries() int {
	valStr := r.getModel("llm_local_retries", "3")
	var val int
	fmt.Sscanf(valStr, "%d", &val)
	if val <= 0 {
		val = 3
	}
	return val
}

func (r *Router) getRemoteEndpoint() string {
	return r.getModel("llm_remote_endpoint", r.RemoteEndpoint)
}

func (r *Router) getRemoteAPIKey() string {
	return r.getModel("llm_remote_api_key", r.RemoteAPIKey)
}

func (r *Router) getComplexContextWindow() int {
	valStr := r.getModel("llm_complex_context_window", "")
	if valStr == "" {
		return r.getLocalContextWindow()
	}
	var val int
	fmt.Sscanf(valStr, "%d", &val)
	if val <= 0 {
		return r.getLocalContextWindow()
	}
	return val
}

func (r *Router) getSystemPrompt() string {
	return r.getModel("llm_system_prompt", "You are a professional coding assistant and project orchestrator.")
}

type Classification string

const (
	Simple  Classification = "SIMPLE"
	Complex Classification = "COMPLEX"
	DTO     Classification = "DTO"
)

const defaultClassifyPrompt = `Classify the following task as either SIMPLE or COMPLEX.
SIMPLE: Short tasks, basic text processing, simple questions.
COMPLEX: Tasks involving code, large data volumes, multiple steps, or deep reasoning.

Task: %s

Respond with ONLY the word SIMPLE, COMPLEX, or DTO.`

func (r *Router) getClassifyPrompt() string {
	return r.getModel("prompt_classify", defaultClassifyPrompt)
}

// getRoutingTarget reads routing_simple / routing_complex / routing_dto from settings.
// Returns "local" or "remote".
func (r *Router) getRoutingTarget(classification Classification) string {
	key := "routing_simple"
	def := "local"
	
	if classification == Complex {
		key = "routing_complex"
		def = "remote"
	} else if classification == DTO {
		key = "routing_dto"
		def = "local" // DTO always defaults to local for reliability
	}
	
	return r.getModel(key, def)
}

// Classify determines if a task is simple or complex using the local LLM
func (r *Router) Classify(ctx context.Context, taskDesc string) (Classification, error) {
	start := time.Now()
	defer func() {
		monitor.LLMLatency.WithLabelValues("local", "classify").Observe(time.Since(start).Seconds())
	}()
	monitor.LLMCalls.WithLabelValues("local", "classify").Inc()

	prompt := fmt.Sprintf(r.getClassifyPrompt(), taskDesc)

	payload := map[string]interface{}{
		"model": r.getLocalModel(),
		"messages": []map[string]string{
			{"role": "user", "content": prompt},
		},
		"temperature": 0,
	}

	jsonData, err := json.Marshal(payload)
	if err != nil {
		return "", err
	}

	req, err := http.NewRequestWithContext(ctx, "POST", r.LocalEndpoint+"/v1/chat/completions", bytes.NewBuffer(jsonData))
	if err != nil {
		return "", err
	}

	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		log.Printf("LLM Router: local classification request failed: %v", err)
		return "", err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		log.Printf("LLM Router: local classification returned status %d", resp.StatusCode)
		return "", fmt.Errorf("local llm error: status %d", resp.StatusCode)
	}

	var result struct {
		Choices []struct {
			Message struct {
				Content string `json:"content"`
			} `json:"message"`
		} `json:"choices"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return "", err
	}

	if len(result.Choices) == 0 {
		return "", fmt.Errorf("no response from LLM")
	}

	content := result.Choices[0].Message.Content
	if content == "COMPLEX" {
		return Complex, nil
	}
	return Simple, nil
}

func (r *Router) GenerateResponse(ctx context.Context, classification Classification, prompt string) (string, error) {
	return r.GenerateChat(ctx, classification, []map[string]string{
		{"role": "user", "content": prompt},
	}, "")
}

func (r *Router) GenerateChat(ctx context.Context, classification Classification, messages []map[string]string, preferredProvider string) (string, error) {
	var endpoint, model, apiKey, provider string

	target := r.getRoutingTarget(classification)
	if preferredProvider == "remote" {
		target = "remote"
	} else if preferredProvider == "local" {
		target = "local"
	}

	if target == "remote" && r.getRemoteEndpoint() != "" {
		endpoint = r.getRemoteEndpoint()
		model = r.getRemoteModel()
		apiKey = r.getRemoteAPIKey()
		provider = "remote"
		log.Printf("LLM Router: Routing %s task to REMOTE provider (%s)", classification, model)
	} else {
		if target == "remote" && r.getRemoteEndpoint() == "" {
			log.Printf("LLM Router: Remote LLM not configured, falling back to LOCAL for %s task", classification)
		} else {
			log.Printf("LLM Router: Routing %s task to LOCAL provider", classification)
		}
		endpoint = r.LocalEndpoint
		model = r.getLocalModel()
		provider = "local"
	}

	start := time.Now()
	defer func() {
		monitor.LLMLatency.WithLabelValues(provider, string(classification)).Observe(time.Since(start).Seconds())
	}()
	monitor.LLMCalls.WithLabelValues(provider, string(classification)).Inc()

	// Prepend system prompt if not present
	hasSystem := false
	for _, m := range messages {
		if m["role"] == "system" {
			hasSystem = true
			break
		}
	}
	if !hasSystem {
		messages = append([]map[string]string{{"role": "system", "content": r.getSystemPrompt()}}, messages...)
	}

	tryEndpoint := func(ep, mdl, key, prov string) (string, error) {
		msgs := messages
		pl := map[string]interface{}{
			"model":    mdl,
			"messages": msgs,
		}
		if prov == "local" {
			temp := r.getLocalTemperature()
			ctxWin := r.getLocalContextWindow()
			if classification == Complex {
				ctxWin = r.getComplexContextWindow()
			}
			pl["temperature"] = temp
			pl["num_ctx"] = ctxWin
			// Ollama specific options block for extra compatibility
			pl["options"] = map[string]interface{}{
				"temperature": temp,
				"num_ctx":     ctxWin,
			}
		}
		jd, _ := json.Marshal(pl)

		timeout := r.getLocalTimeout()
		if classification == DTO {
			timeout = r.getDTOTimeout()
		}
		log.Printf("LLM Router: [%s] %s call, timeout=%v", prov, classification, timeout)

		var lastErr error
		maxRetries := r.getLocalRetries()
		for i := 0; i < maxRetries; i++ {
			req, _ := http.NewRequestWithContext(ctx, "POST", ep+"/v1/chat/completions", bytes.NewBuffer(jd))
			req.Header.Set("Content-Type", "application/json")
			if key != "" {
				req.Header.Set("Authorization", "Bearer "+key)
			}

			client := &http.Client{Timeout: timeout}
			resp, err := client.Do(req)
			if err != nil {
				log.Printf("LLM Router: [%s] attempt %d failed: %v", prov, i+1, err)
				lastErr = err
				time.Sleep(time.Duration(i+1) * time.Second)
				continue
			}
			defer resp.Body.Close()

			if resp.StatusCode != http.StatusOK {
				body, _ := io.ReadAll(io.LimitReader(resp.Body, 1024))
				log.Printf("LLM Router: [%s] attempt %d returned status %d: %s", prov, i+1, resp.StatusCode, strings.TrimSpace(string(body)))
				lastErr = fmt.Errorf("llm api error: status %d: %s", resp.StatusCode, strings.TrimSpace(string(body)))
				// 401/403 are auth errors — no point retrying
				if resp.StatusCode == http.StatusUnauthorized || resp.StatusCode == http.StatusForbidden {
					return "", lastErr
				}
				time.Sleep(time.Duration(i+1) * time.Second)
				continue
			}

			var result struct {
				Choices []struct {
					Message struct {
						Content string `json:"content"`
					} `json:"message"`
				} `json:"choices"`
			}
			if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
				return "", err
			}
			if len(result.Choices) == 0 {
				return "", fmt.Errorf("no response from LLM")
			}
			return result.Choices[0].Message.Content, nil
		}
		return "", fmt.Errorf("failed after %d attempts: %v", maxRetries, lastErr)
	}

	// For local Ollama calls: pause the embedding pipeline so inference is not
	// starved by an in-progress DTO indexing run. The lock is acquired here
	// (after routing decision) so remote-only calls are unaffected.
	localLockHeld := false
	acquireLocalLock := func() {
		if !localLockHeld {
			log.Printf("LLM Router: waiting for embedding pause before local inference")
			r.inferMu.Lock()
			localLockHeld = true
			log.Printf("LLM Router: embedding paused, proceeding with local inference")
		}
	}
	releaseLocalLock := func() {
		if localLockHeld {
			r.inferMu.Unlock()
			localLockHeld = false
		}
	}
	defer releaseLocalLock()

	if provider == "local" {
		acquireLocalLock()
	}

	content, err := tryEndpoint(endpoint, model, apiKey, provider)
	if err != nil && provider == "remote" && r.LocalEndpoint != "" {
		log.Printf("LLM Router: remote failed (%v), falling back to LOCAL", err)
		acquireLocalLock()
		monitor.LLMCalls.WithLabelValues("local", string(classification)).Inc()
		content, err = tryEndpoint(r.LocalEndpoint, r.getLocalModel(), "", "local")
	}
	if err != nil {
		return "", err
	}
	return content, nil
}

func (r *Router) GenerateChatStream(ctx context.Context, classification Classification, messages []map[string]string, preferredProvider string) (<-chan string, error) {
	var endpoint, model, apiKey, provider string

	target := r.getRoutingTarget(classification)
	if preferredProvider == "remote" {
		target = "remote"
	} else if preferredProvider == "local" {
		target = "local"
	}

	if target == "remote" && r.getRemoteEndpoint() != "" {
		endpoint = r.getRemoteEndpoint()
		model = r.getRemoteModel()
		apiKey = r.getRemoteAPIKey()
		provider = "remote"
	} else {
		endpoint = r.LocalEndpoint
		model = r.getLocalModel()
		provider = "local"
	}

	// Prepend system prompt if not present
	hasSystem := false
	for _, m := range messages {
		if m["role"] == "system" {
			hasSystem = true
			break
		}
	}
	if !hasSystem {
		messages = append([]map[string]string{{"role": "system", "content": r.getSystemPrompt()}}, messages...)
	}

	payload := map[string]interface{}{
		"model":    model,
		"messages": messages,
		"stream":   true,
	}

	if provider == "local" {
		ctxWin := r.getLocalContextWindow()
		if classification == Complex {
			ctxWin = r.getComplexContextWindow()
		}
		payload["temperature"] = r.getLocalTemperature()
		payload["num_ctx"] = ctxWin
	}

	jsonData, _ := json.Marshal(payload)
	req, err := http.NewRequestWithContext(ctx, "POST", endpoint+"/v1/chat/completions", bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	if apiKey != "" {
		req.Header.Set("Authorization", "Bearer "+apiKey)
	}

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}

	if resp.StatusCode != http.StatusOK {
		resp.Body.Close()
		return nil, fmt.Errorf("llm api error: status %d", resp.StatusCode)
	}

	out := make(chan string)
	go func() {
		defer resp.Body.Close()
		defer close(out)

		scanner := bufio.NewScanner(resp.Body)
		for scanner.Scan() {
			line := scanner.Text()
			if !strings.HasPrefix(line, "data: ") {
				continue
			}
			data := strings.TrimPrefix(line, "data: ")
			if data == "[DONE]" {
				return
			}

			var chunk struct {
				Choices []struct {
					Delta struct {
						Content string `json:"content"`
					} `json:"delta"`
				} `json:"choices"`
			}
			if err := json.Unmarshal([]byte(data), &chunk); err != nil {
				continue
			}

			if len(chunk.Choices) > 0 && chunk.Choices[0].Delta.Content != "" {
				select {
				case out <- chunk.Choices[0].Delta.Content:
				case <-ctx.Done():
					return
				}
			}
		}
	}()

	return out, nil
}
