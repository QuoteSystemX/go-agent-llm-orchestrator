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
	ID     string `json:"id"`
	Status string `json:"status"`
}

func (c *JulesClient) StartSession(ctx context.Context, taskName string) (*SessionResponse, error) {
	payload := map[string]string{"task": taskName}
	data, _ := json.Marshal(payload)

	req, _ := http.NewRequestWithContext(ctx, "POST", c.BaseURL+"/sessions", bytes.NewBuffer(data))
	req.Header.Set("Authorization", "Bearer "+c.APIKey)
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusCreated && resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("unexpected status: %d", resp.StatusCode)
	}

	var sr SessionResponse
	json.NewDecoder(resp.Body).Decode(&sr)
	return &sr, nil
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
