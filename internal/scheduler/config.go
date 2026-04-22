package scheduler

import (
	"context"
	"io/ioutil"
	"log"

	"gopkg.in/yaml.v2"
)

type Config struct {
	Repositories []Repository `yaml:"repositories"`
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
	for _, repo := range cfg.Repositories {
		for _, task := range repo.Tasks {
			// Generate a unique ID for the task: repo_name:agent:pattern
			taskID := repo.Name + ":" + task.Agent + ":" + task.Pattern
			
			// Insert or Update in DB
			_, err := e.db.ExecContext(ctx, `
				INSERT INTO tasks (id, name, pattern, schedule, mission, status) 
				VALUES (?, ?, ?, ?, ?, 'PENDING')
				ON CONFLICT(id) DO UPDATE SET 
					schedule = excluded.schedule,
					mission = excluded.mission,
					pattern = excluded.pattern,
					name = excluded.name
			`, taskID, repo.Name, task.Pattern, task.Schedule, task.Mission)
			
			if err != nil {
				log.Printf("Failed to import task %s: %v", taskID, err)
			}
		}
	}

	log.Printf("Imported tasks from %s", path)
	return e.SyncTasks(ctx)
}
