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
			Status          string       `json:"status"`
			Model           *OllamaModel `json:"model,omitempty"`
			EmbeddingModel  *OllamaModel `json:"embedding_model,omitempty"`
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
	if m.db != nil {
		endpoint = m.db.GetSetting("llm_local_endpoint", endpoint)
	}
	if endpoint == "" {
		endpoint = "http://localhost:11434"
	}
	targetModel := os.Getenv("LLM_LOCAL_MODEL")
	if m.db != nil {
		targetModel = m.db.GetSetting("llm_local_model", targetModel)
	}

	embeddingModel := os.Getenv("LLM_EMBEDDING_MODEL")
	if m.db != nil {
		embeddingModel = m.db.GetSetting("llm_embedding_model", embeddingModel)
	}
	if embeddingModel == "" {
		embeddingModel = "nomic-embed-text"
	}

	resp, err := m.client.Get(endpoint + "/api/tags")
	if err == nil {
		defer resp.Body.Close()
		var tags OllamaTagsResponse
		if err := json.NewDecoder(resp.Body).Decode(&tags); err == nil {
			hasMain := false
			hasEmbed := false
			for _, model := range tags.Models {
				// We need a local copy for safe pointer reference
				mCopy := model
				if mCopy.Name == targetModel || mCopy.Model == targetModel {
					hasMain = true
					newStatus.Components.Ollama.Model = &mCopy
				}
				if mCopy.Name == embeddingModel || mCopy.Model == embeddingModel {
					hasEmbed = true
					newStatus.Components.Ollama.EmbeddingModel = &mCopy
				}
			}
			
			if hasMain && hasEmbed {
				newStatus.Components.Ollama.Status = "READY"
			} else if hasMain {
				newStatus.Components.Ollama.Status = "MISSING_EMBEDDING_MODEL"
			} else if hasEmbed {
				newStatus.Components.Ollama.Status = "MISSING_MAIN_MODEL"
			} else {
				newStatus.Components.Ollama.Status = "MISSING_ALL_MODELS"
			}
		}
	} else {
		newStatus.Components.Ollama.Status = "DISCONNECTED"
	}

	// 2. Check Remote LLM
	remoteEndpoint := os.Getenv("LLM_REMOTE_ENDPOINT")
	remoteAPIKey := os.Getenv("LLM_REMOTE_API_KEY")
	
	if remoteEndpoint == "" && m.db != nil {
		remoteEndpoint = m.db.GetSetting("llm_remote_endpoint", "")
	}
	if remoteAPIKey == "" && m.db != nil {
		remoteAPIKey = m.db.GetSetting("llm_remote_api_key", "")
	}

	if remoteEndpoint != "" {
		req, err := http.NewRequest("GET", remoteEndpoint+"/models", nil)
		if err == nil {
			if remoteAPIKey != "" {
				req.Header.Set("Authorization", "Bearer "+remoteAPIKey)
			}
			resp, err := m.client.Do(req)
			if err == nil {
				defer resp.Body.Close()
				if resp.StatusCode == http.StatusOK {
					newStatus.Components.Remote.Status = "READY"
				} else if resp.StatusCode == http.StatusUnauthorized || resp.StatusCode == http.StatusForbidden {
					newStatus.Components.Remote.Status = "UNAUTHORIZED"
				} else {
					newStatus.Components.Remote.Status = "ERROR"
				}
			} else {
				newStatus.Components.Remote.Status = "UNREACHABLE"
			}
		} else {
			newStatus.Components.Remote.Status = "INVALID_URL"
		}
	}

	// Overall Status Logic
	if newStatus.Components.Ollama.Status == "READY" || newStatus.Components.Remote.Status == "READY" {
		newStatus.Status = "OK"
	}

	m.mu.Lock()
	m.status = newStatus
	m.mu.Unlock()
}
