package api

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
)

type JulesClient struct {
	BaseURL string
	APIKey  string
	client  *http.Client
}

func NewJulesClient() *JulesClient {
	return &JulesClient{
		BaseURL: os.Getenv("JULES_API_URL"),
		APIKey:  os.Getenv("JULES_API_KEY"),
		client:  &http.Client{},
	}
}

type SessionResponse struct {
	ID      string `json:"id"`
	Status  string `json:"status"`
	Result  string `json:"result,omitempty"`
	Message string `json:"message,omitempty"`
}

func (c *JulesClient) StartSession(ctx context.Context, taskID, mission, pattern string) (*SessionResponse, []byte, error) {
	payload := map[string]string{
		"task_id": taskID,
		"mission": mission,
		"pattern": pattern,
	}
	data, _ := json.Marshal(payload)

	req, _ := http.NewRequestWithContext(ctx, "POST", c.BaseURL+"/sessions", bytes.NewBuffer(data))
	req.Header.Set("Authorization", "Bearer "+c.APIKey)
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.client.Do(req)
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
	
	return &sr, bodyBuf.Bytes(), nil
}

func (c *JulesClient) GetStatus(ctx context.Context, sessionID string) (string, error) {
	req, _ := http.NewRequestWithContext(ctx, "GET", c.BaseURL+"/sessions/"+sessionID, nil)
	req.Header.Set("Authorization", "Bearer "+c.APIKey)

	resp, err := c.client.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	var sr SessionResponse
	json.NewDecoder(resp.Body).Decode(&sr)
	return sr.Status, nil
}
