package main

import "time"

type JobStatus struct {
	ID        string    `json:"id"`
	Name      string    `json:"name"`
	Status    string    `json:"status"` // pending, running, completed, failed
	Progress  int       `json:"progress"`
	Message   string    `json:"message"`
	StartedAt time.Time `json:"startedAt"`
}

type CouncilProposal struct {
	ID          string    `json:"id"`
	Title       string    `json:"title"`
	Proposer    string    `json:"proposer"`
	Votes       int       `json:"votes"`
	Required    int       `json:"required"`
	Status      string    `json:"status"` // open, approved, rejected
	CreatedAt   time.Time `json:"createdAt"`
	CommandType string    `json:"commandType"`
	CommandData string    `json:"commandData"`
}
