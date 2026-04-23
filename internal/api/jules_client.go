package api

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"os"

	"go-agent-llm-orchestrator/internal/db"
	"go-agent-llm-orchestrator/internal/llm"
)

type JulesClient struct {
	BaseURL string
	APIKey  string
	db      *db.DB
	client  *http.Client
}

func NewJulesClient(database *db.DB) *JulesClient {
	return &JulesClient{
		BaseURL: os.Getenv("JULES_API_URL"),
		APIKey:  os.Getenv("JULES_API_KEY"),
		db:      database,
		client:  &http.Client{},
	}
}

func (c *JulesClient) getAPIKey() string {
	if c.db != nil {
		var val string
		if err := c.db.QueryRow("SELECT value FROM settings WHERE key = 'jules_api_key'").Scan(&val); err == nil && val != "" {
			return val
		}
	}
	return c.APIKey
}

func (c *JulesClient) getBaseURL() string {
	if c.db != nil {
		var val string
		if err := c.db.QueryRow("SELECT value FROM settings WHERE key = 'jules_base_url'").Scan(&val); err == nil && val != "" {
			return val
		}
	}
	if c.BaseURL != "" {
		return c.BaseURL
	}
	return "https://jules.googleapis.com/v1alpha"
}

// SessionRequest is the full Jules API payload for creating a session.
type SessionRequest struct {
	Prompt         string        `json:"prompt"`
	SourceContext  SourceContext `json:"sourceContext"`
	AutomationMode string        `json:"automationMode"`
	Title          string        `json:"title"`
}

type SourceContext struct {
	Source            string            `json:"source"`
	GithubRepoContext GithubRepoContext  `json:"githubRepoContext"`
}

type GithubRepoContext struct {
	StartingBranch string `json:"startingBranch"`
}

type SessionResponse struct {
	ID      string `json:"id"`
	Name    string `json:"name"`   // Jules returns "name" as the session identifier
	Status  string `json:"status"`
	Result  string `json:"result,omitempty"`
	Message string `json:"message,omitempty"`
}

// GetSession satisfies llm.JulesClientIface
func (c *JulesClient) GetSession(ctx context.Context, sessionID string) (*llm.SessionInfo, error) {
	req, err := http.NewRequestWithContext(ctx, "GET", c.getBaseURL()+"/sessions/"+sessionID, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("X-Goog-Api-Key", c.getAPIKey())

	resp, err := c.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("jules API error: status %d", resp.StatusCode)
	}

	var sr SessionResponse
	if err := json.NewDecoder(resp.Body).Decode(&sr); err != nil {
		return nil, err
	}
	return &llm.SessionInfo{
		Status:  sr.Status,
		Message: sr.Message,
		Result:  sr.Result,
	}, nil
}

// StartSession creates a Jules session with the full prompt and source context.
// repoName should be e.g. "QuoteSystemX/RecipientOFQuotes".
func (c *JulesClient) StartSession(ctx context.Context, req SessionRequest) (*SessionResponse, []byte, error) {
	baseURL := c.getBaseURL()
	if baseURL == "" {
		return nil, nil, fmt.Errorf("Jules base URL is not configured — set it in Settings → Jules API")
	}
	apiKey := c.getAPIKey()
	if apiKey == "" {
		return nil, nil, fmt.Errorf("Jules API key is not configured — set it in Settings → Jules API")
	}

	data, err := json.Marshal(req)
	if err != nil {
		return nil, nil, err
	}

	httpReq, err := http.NewRequestWithContext(ctx, "POST", baseURL+"/sessions", bytes.NewBuffer(data))
	if err != nil {
		return nil, data, err
	}
	httpReq.Header.Set("X-Goog-Api-Key", apiKey)
	httpReq.Header.Set("Content-Type", "application/json")

	resp, err := c.client.Do(httpReq)
	if err != nil {
		return nil, data, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusCreated && resp.StatusCode != http.StatusOK {
		return nil, data, fmt.Errorf("unexpected status: %d", resp.StatusCode)
	}

	var sr SessionResponse
	var bodyBuf bytes.Buffer
	bodyBuf.ReadFrom(resp.Body)

	if err := json.Unmarshal(bodyBuf.Bytes(), &sr); err != nil {
		return nil, data, err
	}

	// Jules returns the session name like "sessions/abc123"; use it as ID
	if sr.ID == "" && sr.Name != "" {
		sr.ID = sr.Name
	}

	return &sr, bodyBuf.Bytes(), nil
}

func (c *JulesClient) GetStatus(ctx context.Context, sessionID string) (string, error) {
	req, err := http.NewRequestWithContext(ctx, "GET", c.getBaseURL()+"/sessions/"+sessionID, nil)
	if err != nil {
		return "", err
	}
	req.Header.Set("X-Goog-Api-Key", c.getAPIKey())

	resp, err := c.client.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("jules API error: status %d", resp.StatusCode)
	}

	var sr SessionResponse
	if err := json.NewDecoder(resp.Body).Decode(&sr); err != nil {
		return "", err
	}
	return sr.Status, nil
}

func (c *JulesClient) SendMessage(ctx context.Context, sessionID, prompt string) error {
	payload := map[string]string{"prompt": prompt}
	data, _ := json.Marshal(payload)

	req, err := http.NewRequestWithContext(ctx, "POST",
		c.getBaseURL()+"/sessions/"+sessionID+":sendMessage", bytes.NewBuffer(data))
	if err != nil {
		return err
	}
	req.Header.Set("X-Goog-Api-Key", c.getAPIKey())
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("jules sendMessage error: status %d", resp.StatusCode)
	}
	return nil
}

func (c *JulesClient) ApprovePlan(ctx context.Context, sessionID string) error {
	req, err := http.NewRequestWithContext(ctx, "POST",
		c.getBaseURL()+"/sessions/"+sessionID+":approvePlan", bytes.NewBuffer([]byte("{}")))
	if err != nil {
		return err
	}
	req.Header.Set("X-Goog-Api-Key", c.getAPIKey())
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("jules approvePlan error: status %d", resp.StatusCode)
	}
	return nil
}

func (c *JulesClient) ListSessions(ctx context.Context) ([]SessionResponse, error) {
	req, err := http.NewRequestWithContext(ctx, "GET", c.getBaseURL()+"/sessions", nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("X-Goog-Api-Key", c.getAPIKey())

	resp, err := c.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("jules listSessions error: status %d", resp.StatusCode)
	}

	var result struct {
		Sessions []SessionResponse `json:"sessions"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, err
	}
	return result.Sessions, nil
}
