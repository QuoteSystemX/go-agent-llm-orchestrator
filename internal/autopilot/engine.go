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

	basePath := e.db.GetSetting("repo_base_path", "./data/repos")
	
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
			// Check if a draft already exists to avoid duplication
			var exists int
			err := e.db.QueryRow("SELECT COUNT(*) FROM tasks WHERE name = ? AND status = 'DRAFT' AND pattern = 'discovery'", repoName).Scan(&exists)
			if err == nil && exists == 0 {
				log.Printf("Autopilot: Proposing discovery for %s", repoName)
				e.ProposeIdea(repoName, "project-planner", "discovery", "/discovery and audit", "@daily", 5)
			}
		}
	}
}

func (e *Engine) getManagedRepos() ([]string, error) {
	// Only get real repositories, not draft task names
	rows, err := e.db.Query("SELECT DISTINCT name FROM tasks WHERE name NOT LIKE 'draft-%'")
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

func (e *Engine) ProposeIdea(repoName, agent, pattern, mission, schedule string, importance int) error {
	// Clean repo name for ID (replace slashes with underscores)
	safeRepo := strings.ReplaceAll(repoName, "/", "_")
	id := fmt.Sprintf("draft-%s-%d", safeRepo, time.Now().Unix())
	
	// 1. Create a DRAFT task
	_, err := e.db.Exec(`
		INSERT INTO tasks (id, name, agent, pattern, mission, schedule, status, importance, category) 
		VALUES (?, ?, ?, ?, ?, ?, 'DRAFT', ?, 'worker')`,
		id, repoName, agent, pattern, mission, schedule, importance)
	if err != nil {
		return err
	}

	// 2. Notify in chat
	msg := fmt.Sprintf("💡 **Autopilot Proposal for %s**: I suggest running `%s` with `%s` agent. [Approve/Discard in Tasks]", 
		repoName, mission, agent)
	_, err = e.db.Exec("INSERT INTO web_chat_history (role, content, provider, repo) VALUES ('assistant', ?, 'autopilot', ?)", 
		msg, repoName)
	
	return err
}
