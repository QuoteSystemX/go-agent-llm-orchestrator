package llm

import (
	"bytes"
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"strings"
	"time"

	"go-agent-llm-orchestrator/internal/db"
	"go-agent-llm-orchestrator/internal/monitor"
)

type Router struct {
	db             *db.DB
	LocalEndpoint  string
	RemoteEndpoint string
	RemoteAPIKey   string
}

func NewRouter(database *db.DB) *Router {
	return &Router{
		db:             database,
		LocalEndpoint:  os.Getenv("LLM_LOCAL_ENDPOINT"),
		RemoteEndpoint: os.Getenv("LLM_REMOTE_ENDPOINT"),
		RemoteAPIKey:   os.Getenv("LLM_REMOTE_API_KEY"),
	}
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
	return r.getModel("llm_local_model", os.Getenv("LLM_LOCAL_MODEL"))
}

func (r *Router) getRemoteModel() string {
	return r.getModel("llm_remote_model", os.Getenv("LLM_REMOTE_MODEL"))
}

func (r *Router) getLocalContextWindow() int {
	valStr := r.getModel("llm_local_context_window", "32768")
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
	valStr := r.getModel("llm_local_timeout", "300")
	var val int
	fmt.Sscanf(valStr, "%d", &val)
	if val <= 0 {
		val = 300
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

		var lastErr error
		maxRetries := r.getLocalRetries()
		for i := 0; i < maxRetries; i++ {
			req, _ := http.NewRequestWithContext(ctx, "POST", ep+"/v1/chat/completions", bytes.NewBuffer(jd))
			req.Header.Set("Content-Type", "application/json")
			if key != "" {
				req.Header.Set("Authorization", "Bearer "+key)
			}

			client := &http.Client{Timeout: r.getLocalTimeout()}
			resp, err := client.Do(req)
			if err != nil {
				log.Printf("LLM Router: [%s] attempt %d failed: %v", prov, i+1, err)
				lastErr = err
				time.Sleep(time.Duration(i+1) * time.Second)
				continue
			}
			defer resp.Body.Close()

			if resp.StatusCode != http.StatusOK {
				log.Printf("LLM Router: [%s] attempt %d returned status %d", prov, i+1, resp.StatusCode)
				lastErr = fmt.Errorf("llm api error: status %d", resp.StatusCode)
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

	content, err := tryEndpoint(endpoint, model, apiKey, provider)
	if err != nil && provider == "remote" && r.LocalEndpoint != "" {
		log.Printf("LLM Router: remote failed (%v), falling back to LOCAL", err)
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
