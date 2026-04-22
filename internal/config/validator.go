package config

import (
	"fmt"

	"github.com/robfig/cron/v3"
)

type TaskConfig struct {
	Name     string `yaml:"name"`
	Agent    string `yaml:"agent"`
	Pattern  string `yaml:"pattern"`
	Mission  string `yaml:"mission"`
	Schedule string `yaml:"schedule"`
}

func ValidateTask(t TaskConfig) error {
	if t.Name == "" {
		return fmt.Errorf("task name is required")
	}
	if t.Schedule == "" {
		return fmt.Errorf("task schedule is required")
	}

	// Validate Cron expression
	parser := cron.NewParser(cron.Minute | cron.Hour | cron.Dom | cron.Month | cron.Dow)
	if _, err := parser.Parse(t.Schedule); err != nil {
		return fmt.Errorf("invalid cron schedule '%s': %v", t.Schedule, err)
	}

	return nil
}
