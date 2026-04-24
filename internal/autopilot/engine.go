package autopilot

import (
	"context"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"time"

	"go-agent-llm-orchestrator/internal/db"
	"go-agent-llm-orchestrator/internal/monitor"
	"go-agent-llm-orchestrator/internal/scheduler"
)

type Engine struct {
	db        *db.DB
	scheduler *scheduler.Engine
	stats     *monitor.StatsAggregator
}

func NewEngine(database *db.DB, sched *scheduler.Engine, stats *monitor.StatsAggregator) *Engine {
	return &Engine{
		db:        database,
		scheduler: sched,
		stats:     stats,
	}
}

func (e *Engine) Start(ctx context.Context) {
	ticker := time.NewTicker(10 * time.Minute)
	defer ticker.Stop()

	log.Println("Autopilot Engine started (Interval: 10m)")

	// Initial run
	e.Run(ctx)

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			e.Run(ctx)
		}
	}
}

func (e *Engine) Run(ctx context.Context) {
	log.Println("Autopilot Cycle: Analyzing task backlogs...")

	basePath := e.db.GetSetting("repo_base_path", "./repos")
	
	// Get unique repos from tasks
	repos, err := e.getManagedRepos()
	if err != nil {
		log.Printf("Autopilot Error: failed to get repos: %v", err)
		return
	}

	for _, repoName := range repos {
		taskPath := filepath.Join(basePath, repoName, "tasks")
		count := e.countTasks(taskPath)

		log.Printf("Autopilot: Repo [%s] has %d tasks in backlog", repoName, count)

		if count > 0 {
			e.scaleUp(repoName, count)
		} else {
			e.scaleDown(repoName)
		}
	}
}

func (e *Engine) getManagedRepos() ([]string, error) {
	rows, err := e.db.Query("SELECT DISTINCT name FROM tasks")
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var repos []string
	for rows.Next() {
		var name string
		if err := rows.Scan(&name); err == nil {
			repos = append(repos, name)
		}
	}
	return repos, nil
}

func (e *Engine) countTasks(path string) int {
	files, err := os.ReadDir(path)
	if err != nil {
		return 0
	}
	count := 0
	for _, f := range files {
		if !f.IsDir() && (filepath.Ext(f.Name()) == ".md" || filepath.Ext(f.Name()) == ".json") {
			count++
		}
	}
	return count
}

func (e *Engine) scaleUp(repoName string, count int) {
	// Enable workers for this repo
	_, err := e.db.Exec("UPDATE tasks SET status = 'PENDING' WHERE name = ? AND category = 'worker' AND status = 'PAUSED'", repoName)
	if err != nil {
		log.Printf("Autopilot ScaleUp Error [%s]: %v", repoName, err)
	} else {
		log.Printf("Autopilot: Activated workers for %s due to %d tasks", repoName, count)
	}
}

func (e *Engine) scaleDown(repoName string) {
	// Disable workers for this repo (if they are not running)
	_, err := e.db.Exec("UPDATE tasks SET status = 'PAUSED' WHERE name = ? AND category = 'worker' AND status = 'PENDING'", repoName)
	if err != nil {
		log.Printf("Autopilot ScaleDown Error [%s]: %v", repoName, err)
	} else {
		log.Printf("Autopilot: Paused idle workers for %s", repoName)
	}
}

func (e *Engine) ProposeIdea(repoName, content string) error {
	_, err := e.db.Exec("INSERT INTO web_chat_history (role, content, provider, repo) VALUES ('assistant', ?, 'autopilot', ?)", 
		fmt.Sprintf("💡 **Autopilot Idea for %s**: %s", repoName, content), repoName)
	return err
}
