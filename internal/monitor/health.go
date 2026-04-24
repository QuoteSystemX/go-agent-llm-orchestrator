package monitor

import (
	"encoding/json"
	"net/http"
	"os"
	"sync"
	"time"

	"go-agent-llm-orchestrator/internal/db"
)

type OllamaModel struct {
	Name     string `json:"name"`
	Model    string `json:"model"`
	Size     int64  `json:"size"`
	Details  any    `json:"details"`
}

type OllamaTagsResponse struct {
	Models []OllamaModel `json:"models"`
}

type HealthStatus struct {
	Status     string `json:"status"`
	Components struct {
		Ollama struct {
			Status string       `json:"status"`
			Model  *OllamaModel `json:"model,omitempty"`
		} `json:"ollama"`
		Remote struct {
			Status string `json:"status"`
		} `json:"remote"`
	} `json:"components"`
}

type HealthMonitor struct {
	status HealthStatus
	mu     sync.RWMutex
	client *http.Client
	db     *db.DB
}

func NewHealthMonitor(database *db.DB) *HealthMonitor {
	return &HealthMonitor{
		client: &http.Client{Timeout: 5 * time.Second},
		db:     database,
	}
}

func (m *HealthMonitor) Start() {
	go func() {
		for {
			m.check()
			time.Sleep(30 * time.Second)
		}
	}()
}

func (m *HealthMonitor) GetStatus() HealthStatus {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.status
}

func (m *HealthMonitor) check() {
	newStatus := HealthStatus{Status: "ERROR"}
	newStatus.Components.Ollama.Status = "NOT_READY"
	newStatus.Components.Remote.Status = "NOT_CONFIGURED"

	// 1. Check Local Ollama
	endpoint := os.Getenv("LLM_LOCAL_ENDPOINT")
	if endpoint == "" {
		endpoint = "http://localhost:11434"
	}
	targetModel := os.Getenv("LLM_LOCAL_MODEL")
	if targetModel == "" {
		targetModel = "phi3:mini"
	}

	resp, err := m.client.Get(endpoint + "/api/tags")
	if err == nil {
		defer resp.Body.Close()
		var tags OllamaTagsResponse
		if err := json.NewDecoder(resp.Body).Decode(&tags); err == nil {
			for _, model := range tags.Models {
				if model.Name == targetModel || model.Model == targetModel {
					newStatus.Components.Ollama.Status = "READY"
					newStatus.Components.Ollama.Model = &model
					break
				}
			}
		}
	} else {
		newStatus.Components.Ollama.Status = "DISCONNECTED"
	}

	// 2. Check Remote LLM
	remoteEndpoint := ""
	if m.db != nil {
		remoteEndpoint = m.db.GetSetting("llm_remote_endpoint", os.Getenv("LLM_REMOTE_ENDPOINT"))
	}

	if remoteEndpoint != "" {
		newStatus.Components.Remote.Status = "READY" // Basic assumption if configured
		// Optional: Perform a dummy request to verify key
	}

	// Overall Status Logic
	if newStatus.Components.Ollama.Status == "READY" || newStatus.Components.Remote.Status == "READY" {
		newStatus.Status = "OK"
	}

	m.mu.Lock()
	m.status = newStatus
	m.mu.Unlock()
}
