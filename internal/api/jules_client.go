package api

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
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
	return c.BaseURL
}

// EffectiveBaseURL returns the Jules API base URL that will actually be used.
func (c *JulesClient) EffectiveBaseURL() string {
	return c.getBaseURL()
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
	Status  string `json:"state"`
	Result  string `json:"result,omitempty"`
	Message string `json:"message,omitempty"`
}

// doRequest is a helper for making authenticated HTTP requests to the Jules API
func (c *JulesClient) doRequest(ctx context.Context, method, path string, body io.Reader) (*http.Response, error) {
	baseURL := c.getBaseURL()
	if baseURL == "" {
		return nil, fmt.Errorf("Jules base URL is not configured — set it in Settings → Jules API")
	}
	apiKey := c.getAPIKey()
	if apiKey == "" {
		return nil, fmt.Errorf("Jules API key is not configured — set it in Settings → Jules API")
	}

	req, err := http.NewRequestWithContext(ctx, method, baseURL+path, body)
	if err != nil {
		return nil, err
	}
	req.Header.Set("X-Goog-Api-Key", apiKey)
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}

	return c.client.Do(req)
}

// GetSession satisfies llm.JulesClientIface
func (c *JulesClient) GetSession(ctx context.Context, sessionID string) (*llm.SessionInfo, error) {
	resp, err := c.doRequest(ctx, http.MethodGet, "/sessions/"+sessionID, nil)
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
	data, err := json.Marshal(req)
	if err != nil {
		return nil, nil, err
	}

	resp, err := c.doRequest(ctx, http.MethodPost, "/sessions", bytes.NewBuffer(data))
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
	session, err := c.GetSession(ctx, sessionID)
	if err != nil {
		return "", err
	}
	return session.Status, nil
}

func (c *JulesClient) SendMessage(ctx context.Context, sessionID, prompt string) error {
	payload := map[string]string{"prompt": prompt}
	data, _ := json.Marshal(payload)

	resp, err := c.doRequest(ctx, http.MethodPost, "/sessions/"+sessionID+":sendMessage", bytes.NewBuffer(data))
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
	resp, err := c.doRequest(ctx, http.MethodPost, "/sessions/"+sessionID+":approvePlan", bytes.NewBuffer([]byte("{}")))
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
	resp, err := c.doRequest(ctx, http.MethodGet, "/sessions", nil)
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
