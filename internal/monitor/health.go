package monitor

import (
	"encoding/json"
	"log"
	"net/http"
	"os"
	"sync"
	"time"
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
	Status     string       `json:"status"`
	Components struct {
		Ollama struct {
			Status string      `json:"status"`
			Model  *OllamaModel `json:"model,omitempty"`
		} `json:"ollama"`
	} `json:"components"`
}

type HealthMonitor struct {
	status HealthStatus
	mu     sync.RWMutex
	client *http.Client
}

func NewHealthMonitor() *HealthMonitor {
	return &HealthMonitor{
		client: &http.Client{Timeout: 5 * time.Second},
	}
}

func (m *HealthMonitor) Start() {
	go func() {
		for {
			m.check()
			time.Sleep(15 * time.Second)
		}
	}()
}

func (m *HealthMonitor) GetStatus() HealthStatus {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.status
}

func (m *HealthMonitor) check() {
	newStatus := HealthStatus{Status: "OK"}
	newStatus.Components.Ollama.Status = "NOT_READY"

	endpoint := os.Getenv("LLM_LOCAL_ENDPOINT")
	if endpoint == "" {
		endpoint = "http://localhost:11434"
	}
	targetModel := os.Getenv("LLM_LOCAL_MODEL")
	if targetModel == "" {
		targetModel = "phi3:mini"
	}

	resp, err := m.client.Get(endpoint + "/api/tags")
	if err != nil {
		newStatus.Components.Ollama.Status = "DISCONNECTED"
	} else {
		defer resp.Body.Close()
		var tags OllamaTagsResponse
		if err := json.NewDecoder(resp.Body).Decode(&tags); err != nil {
			log.Printf("HealthMonitor: failed to decode ollama tags: %v", err)
		} else {
			for _, model := range tags.Models {
				if model.Name == targetModel || model.Model == targetModel {
					newStatus.Components.Ollama.Status = "READY"
					newStatus.Components.Ollama.Model = &model
					break
				}
			}
		}
	}

	m.mu.Lock()
	m.status = newStatus
	m.mu.Unlock()
}
