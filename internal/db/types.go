package db

type SessionInfo struct {
	Status  string
	Message string
	Result  string
}

type Task struct {
	ID           string
	Name         string // Repo name
	Agent        string
	Mission      string
	Pattern      string
	Schedule     string
	Status       string
	CurrentRetry int
	MaxRetries   int
}
