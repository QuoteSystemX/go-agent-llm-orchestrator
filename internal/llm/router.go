package llm

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
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

type Classification string

const (
	Simple  Classification = "SIMPLE"
	Complex Classification = "COMPLEX"
)

const defaultClassifyPrompt = `Classify the following task as either SIMPLE or COMPLEX.
SIMPLE: Short tasks, basic text processing, simple questions.
COMPLEX: Tasks involving code, large data volumes, multiple steps, or deep reasoning.

Task: %s

Respond with ONLY the word SIMPLE or COMPLEX.`

func (r *Router) getClassifyPrompt() string {
	return r.getModel("prompt_classify", defaultClassifyPrompt)
}

// getRoutingTarget reads routing_simple / routing_complex from settings.
// Returns "local" or "remote".
func (r *Router) getRoutingTarget(classification Classification) string {
	key := "routing_simple"
	def := "local"
	if classification == Complex {
		key = "routing_complex"
		def = "remote"
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
	})
}

func (r *Router) GenerateChat(ctx context.Context, classification Classification, messages []map[string]string) (string, error) {
	var endpoint, model, apiKey, provider string

	target := r.getRoutingTarget(classification)
	if target == "remote" && r.RemoteEndpoint != "" {
		endpoint = r.RemoteEndpoint
		model = r.getRemoteModel()
		apiKey = r.RemoteAPIKey
		provider = "remote"
		log.Printf("LLM Router: Routing %s task to REMOTE provider (%s)", classification, model)
	} else {
		if target == "remote" && r.RemoteEndpoint == "" {
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

	payload := map[string]interface{}{
		"model":    model,
		"messages": messages,
	}

	jsonData, _ := json.Marshal(payload)
	
	// Retry logic for 3 attempts
	var lastErr error
	for i := 0; i < 3; i++ {
		req, _ := http.NewRequestWithContext(ctx, "POST", endpoint+"/v1/chat/completions", bytes.NewBuffer(jsonData))
		req.Header.Set("Content-Type", "application/json")
		if apiKey != "" {
			req.Header.Set("Authorization", "Bearer "+apiKey)
		}

		client := &http.Client{Timeout: 60 * time.Second}
		resp, err := client.Do(req)
		if err != nil {
			log.Printf("LLM Router: request attempt %d failed: %v", i+1, err)
			lastErr = err
			time.Sleep(time.Duration(i+1) * time.Second)
			continue
		}
		defer resp.Body.Close()

		if resp.StatusCode != http.StatusOK {
			log.Printf("LLM Router: request attempt %d returned status %d", i+1, resp.StatusCode)
			lastErr = fmt.Errorf("llm api error: status %d", resp.StatusCode)
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

	return "", fmt.Errorf("failed after 3 attempts: %v", lastErr)
}
