package autopilot

import (
	"context"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"
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

	// Phase 1: Sync Distributed Tasks (tasks/*.md)
	e.syncDistributedTasks(ctx, basePath)

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

func (e *Engine) syncDistributedTasks(ctx context.Context, basePath string) {
	// Discover all repos by walking the basePath (max depth 2 for org/repo)
	err := filepath.WalkDir(basePath, func(path string, d os.DirEntry, err error) error {
		if err != nil || !d.IsDir() {
			return nil
		}

		// Calculate relative path to see if it's a potential repo
		rel, _ := filepath.Rel(basePath, path)
		if rel == "." { return nil }
		
		parts := strings.Split(filepath.ToSlash(rel), "/")
		
		// We are looking for directories that contain a 'tasks' folder.
		// Repo names can be 'my-repo' (depth 1) or 'QuotesystemX/my-repo' (depth 2).
		// We stop scanning deeper than 2 levels.
		if len(parts) > 2 {
			return nil // Don't skip branch, just don't scan deeper
		}

		taskPath := filepath.Join(path, "tasks")
		info, err := os.Stat(taskPath)
		if err != nil || !info.IsDir() {
			return nil // No tasks folder or unreadable
		}

		files, err := os.ReadDir(taskPath)
		if err != nil {
			return nil
		}

		repoName := rel // Use the relative path as the repo name
		for _, f := range files {
			if f.IsDir() || filepath.Ext(f.Name()) != ".md" {
				continue
			}

			content, err := os.ReadFile(filepath.Join(taskPath, f.Name()))
			if err != nil {
				continue
			}

			e.processTaskCard(ctx, repoName, f.Name(), string(content))
		}
		return nil
	})

	if err != nil {
		log.Printf("Autopilot Error during task sync: %v", err)
	}
}

func (e *Engine) processTaskCard(ctx context.Context, repoName, filename, content string) {
	// Skip if already imported (basic idempotency based on filename and repo)
	taskID := fmt.Sprintf("dist-%s-%s", strings.ReplaceAll(repoName, "/", "_"), strings.TrimSuffix(filename, ".md"))
	
	var exists int
	e.db.QueryRow("SELECT COUNT(*) FROM tasks WHERE id = ?", taskID).Scan(&exists)
	if exists > 0 {
		return
	}

	// Simple parser for [STORY] or [BUG]
	isStory := strings.Contains(content, "[STORY]")
	isBug := strings.Contains(content, "[BUG]")
	if !isStory && !isBug {
		return
	}

	// Extract Title/Mission (first line, # header, or [TAG] line)
	mission := ""
	lines := strings.Split(content, "\n")
	for _, l := range lines {
		l = strings.TrimSpace(l)
		if strings.HasPrefix(l, "#") {
			mission = strings.TrimSpace(strings.TrimPrefix(l, "#"))
			break
		}
		if strings.Contains(l, "[STORY]") {
			mission = strings.TrimSpace(strings.Replace(l, "[STORY]", "", 1))
			if mission != "" { break }
		}
		if strings.Contains(l, "[BUG]") {
			mission = strings.TrimSpace(strings.Replace(l, "[BUG]", "", 1))
			if mission != "" { break }
		}
		if l != "" && !strings.Contains(l, "[") {
			mission = l
			break
		}
	}
	if mission == "" {
		mission = filename
	}

	// Pickup Matrix mapping (Expanded)
	agent := "go-specialist" // Default
	lowContent := strings.ToLower(content)
	if isBug {
		agent = "debugger"
	} else if strings.Contains(lowContent, "ui") || strings.Contains(lowContent, "css") || strings.Contains(lowContent, "frontend") || strings.Contains(lowContent, "tailwind") {
		agent = "frontend-specialist"
	} else if strings.Contains(lowContent, "api") || strings.Contains(lowContent, "database") || strings.Contains(lowContent, "sql") || strings.Contains(lowContent, "postgresql") {
		agent = "backend-specialist"
	} else if strings.Contains(lowContent, "audit") || strings.Contains(lowContent, "security") || strings.Contains(lowContent, "vulnerability") || strings.Contains(lowContent, "auth") {
		agent = "security-auditor"
	} else if strings.Contains(lowContent, "k8s") || strings.Contains(lowContent, "kubernetes") || strings.Contains(lowContent, "helm") {
		agent = "k8s-engineer"
	} else if strings.Contains(lowContent, "infra") || strings.Contains(lowContent, "terraform") || strings.Contains(lowContent, "devops") || strings.Contains(lowContent, "ci/cd") {
		agent = "devops-engineer"
	} else if strings.Contains(lowContent, "test") || strings.Contains(lowContent, "qa") || strings.Contains(lowContent, "e2e") {
		agent = "test-engineer"
	} else if strings.Contains(lowContent, "crypto") || strings.Contains(lowContent, "ton") || strings.Contains(lowContent, "blockchain") || strings.Contains(lowContent, "wallet") {
		agent = "crypto-specialist"
	} else if strings.Contains(lowContent, "grpc") || strings.Contains(lowContent, "protobuf") || strings.Contains(lowContent, "buf") {
		agent = "grpc-architect"
	} else if strings.Contains(lowContent, "grafana") || strings.Contains(lowContent, "prometheus") || strings.Contains(lowContent, "monitoring") || strings.Contains(lowContent, "loki") {
		agent = "grafana-master"
	}

	log.Printf("Autopilot: Mining new task from %s/%s -> Agent: %s, Mission: %s", repoName, filename, agent, mission)

	_, err := e.db.Exec(`
		INSERT INTO tasks (id, name, agent, pattern, mission, schedule, status, importance, category) 
		VALUES (?, ?, ?, ?, ?, '@once', 'PENDING', 3, 'worker')`,
		taskID, repoName, agent, "none", mission)
	if err != nil {
		log.Printf("Autopilot Mining Error: %v", err)
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
