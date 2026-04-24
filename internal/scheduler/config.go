package scheduler

import (
	"context"
	"fmt"
	"io/ioutil"
	"log"

	"gopkg.in/yaml.v2"
)

type Config struct {
	PromptLibrary PromptLibraryConfig `yaml:"prompt_library"`
	Repositories  []Repository        `yaml:"repositories"`
}

type PromptLibraryConfig struct {
	Git             GitConfig `yaml:"git"`
	CacheDir        string    `yaml:"cache_dir"`
	RefreshInterval string    `yaml:"refresh_interval"`
}

type GitConfig struct {
	URL        string `yaml:"url"`
	Branch     string `yaml:"branch"`
	SSHKeyPath string `yaml:"ssh_key_path"` // optional; falls back to DB setting
}

type Repository struct {
	Name  string `yaml:"name"`
	Tasks []Task `yaml:"tasks"`
}

type Task struct {
	Agent    string `yaml:"agent"`
	Pattern  string `yaml:"pattern"`
	Mission  string `yaml:"mission"`
	Schedule string `yaml:"schedule"`
}

func (e *Engine) ImportDistribution(path string) error {
	data, err := ioutil.ReadFile(path)
	if err != nil {
		return err
	}

	var cfg Config
	if err := yaml.Unmarshal(data, &cfg); err != nil {
		return err
	}

	ctx := context.Background()

	// Use a transaction for all database operations to avoid SQLITE_BUSY and ensure atomicity
	tx, err := e.db.Begin()
	if err != nil {
		return fmt.Errorf("starting import transaction: %w", err)
	}
	defer tx.Rollback()

	// Persist prompt_library git config to settings so web UI and git syncer can read it
	if cfg.PromptLibrary.Git.URL != "" {
		tx.ExecContext(ctx, "INSERT OR REPLACE INTO settings (key, value) VALUES ('prompt_library_git_url', ?)", cfg.PromptLibrary.Git.URL)
	}
	if cfg.PromptLibrary.Git.Branch != "" {
		tx.ExecContext(ctx, "INSERT OR REPLACE INTO settings (key, value) VALUES ('prompt_library_git_branch', ?)", cfg.PromptLibrary.Git.Branch)
	}
	if cfg.PromptLibrary.CacheDir != "" {
		tx.ExecContext(ctx, "INSERT OR REPLACE INTO settings (key, value) VALUES ('prompt_library_cache_dir', ?)", cfg.PromptLibrary.CacheDir)
	}
	if cfg.PromptLibrary.RefreshInterval != "" {
		tx.ExecContext(ctx, "INSERT OR REPLACE INTO settings (key, value) VALUES ('prompt_library_refresh_interval', ?)", cfg.PromptLibrary.RefreshInterval)
	}
	// SSHKeyPath: read file content and store in DB only if not already set
	if cfg.PromptLibrary.Git.SSHKeyPath != "" {
		if keyData, err := ioutil.ReadFile(cfg.PromptLibrary.Git.SSHKeyPath); err == nil {
			tx.ExecContext(ctx, "INSERT OR IGNORE INTO settings (key, value) VALUES ('prompt_library_ssh_key', ?)", string(keyData))
			log.Printf("Loaded SSH key from %s into DB (INSERT OR IGNORE)", cfg.PromptLibrary.Git.SSHKeyPath)
		} else {
			log.Printf("Warning: could not read SSH key from %s: %v", cfg.PromptLibrary.Git.SSHKeyPath, err)
		}
	}

	for _, repo := range cfg.Repositories {
		for _, task := range repo.Tasks {
			taskID := repo.Name + ":" + task.Agent + ":" + task.Pattern

			_, err := tx.ExecContext(ctx, `
				INSERT INTO tasks (id, name, agent, pattern, schedule, mission, status)
				VALUES (?, ?, ?, ?, ?, ?, 'PENDING')
				ON CONFLICT(id) DO UPDATE SET
					schedule = excluded.schedule,
					mission  = excluded.mission,
					pattern  = excluded.pattern,
					agent    = excluded.agent,
					name     = excluded.name
			`, taskID, repo.Name, task.Agent, task.Pattern, task.Schedule, task.Mission)

			if err != nil {
				log.Printf("Failed to import task %s: %v", taskID, err)
				return err // Fail the whole transaction if a task import fails
			}
		}
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("committing import transaction: %w", err)
	}

	log.Printf("Imported distribution from %s", path)
	return e.SyncTasks(ctx)
}
