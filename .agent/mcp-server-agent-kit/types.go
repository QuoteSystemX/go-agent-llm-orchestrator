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
	Voters      []string  `json:"voters"` // agent identities that have already voted; prevents one caller from casting multiple votes
	Required    int       `json:"required"`
	Status      string    `json:"status"` // open, approved, rejected
	CreatedAt   time.Time `json:"createdAt"`
	CommandType string    `json:"commandType"`
	CommandData string    `json:"commandData"`
}

// VetoRecord tracks an ethics-auditor veto's block state, separately from the CouncilProposal
// that governs lifting it — a veto takes effect immediately on creation (it is a block, not
// something to be approved), only its *lifting* is voted on via CouncilProposal.
type VetoRecord struct {
	ID            string     `json:"id"`
	PlanOrTaskRef string     `json:"planOrTaskRef"`
	Status        string     `json:"status"` // active, lifted
	CreatedBy     string     `json:"createdBy"`
	LiftedBy      string     `json:"liftedBy,omitempty"`
	Reason        string     `json:"reason,omitempty"`
	ProposalID    string     `json:"proposalId"` // the lift-proposal's CouncilProposal.ID
	CreatedAt     time.Time  `json:"createdAt"`
	LiftedAt      *time.Time `json:"liftedAt,omitempty"`
}

type WorkflowInfo struct {
	ID          string `json:"id"`
	Name        string `json:"name"`
	Description string `json:"description"`
	Phase       string `json:"phase"`
	Args        string `json:"args"`
	Executable  bool   `json:"executable"`
}

type RegistryInfo struct {
	ID          string `json:"id"`
	Name        string `json:"name"`
	Description string `json:"description"`
	Type        string `json:"type"` // agent, skill
}
