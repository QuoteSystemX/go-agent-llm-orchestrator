package db

import (
	"context"
	"database/sql"
	_ "embed"
	"fmt"
	"log"
	"os"
	"path/filepath"

	"strings"

	_ "modernc.org/sqlite"
)

//go:embed schema.sql
var schemaSQL string

type DB struct {
	*sql.DB
}

// InitDB initializes the SQLite database at the given path
func InitDB(dbPath string) (*DB, error) {
	// Ensure directory exists
	dir := filepath.Dir(dbPath)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return nil, fmt.Errorf("creating db directory: %w", err)
	}

	db, err := sql.Open("sqlite", dbPath)
	if err != nil {
		return nil, fmt.Errorf("opening sqlite db: %w", err)
	}

	// Limit to 10 concurrent connections to allow multiple readers in WAL mode
	db.SetMaxOpenConns(10)

	// Set WAL mode for better concurrency
	if _, err := db.Exec("PRAGMA journal_mode=WAL;"); err != nil {
		return nil, fmt.Errorf("setting WAL mode: %w", err)
	}

	// Wait up to 5 s instead of returning SQLITE_BUSY immediately
	if _, err := db.Exec("PRAGMA busy_timeout=5000;"); err != nil {
		return nil, fmt.Errorf("setting busy_timeout: %w", err)
	}

	// Initialize schema
	if _, err := db.Exec(schemaSQL); err != nil {
		return nil, fmt.Errorf("initializing schema: %w", err)
	}

	// Migrations: add columns that may not exist in older databases
	migrations := []string{
		`ALTER TABLE tasks ADD COLUMN agent TEXT DEFAULT ''`,
		`ALTER TABLE tasks ADD COLUMN auto_paused INTEGER DEFAULT 0`,
		`ALTER TABLE task_logs ADD COLUMN session_id TEXT`,
		`ALTER TABLE tasks ADD COLUMN importance INTEGER DEFAULT 1`,
		`ALTER TABLE tasks ADD COLUMN category TEXT DEFAULT 'worker'`,
		`ALTER TABLE tasks ADD COLUMN current_stage TEXT DEFAULT 'idle'`,
		`ALTER TABLE tasks ADD COLUMN progress INTEGER DEFAULT 0`,
		`CREATE TABLE IF NOT EXISTS task_run_details (id INTEGER PRIMARY KEY AUTOINCREMENT, log_id INTEGER NOT NULL, phase TEXT NOT NULL, content TEXT, duration_ms INTEGER DEFAULT 0, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)`,
		`CREATE TABLE IF NOT EXISTS web_chat_history (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT NOT NULL, content TEXT NOT NULL, provider TEXT, repo TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)`,
		`CREATE TABLE IF NOT EXISTS templates (name TEXT PRIMARY KEY, content TEXT NOT NULL, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)`,
		`INSERT OR IGNORE INTO templates (name, content) VALUES ('bmad-standard', 'description: "Full BMAD lifecycle: from Discovery to Sprint Closure"
tasks:
  - mission: "/discovery"
    pattern: "discovery"
    agent: "project-planner"
    importance: 10
    category: "service"
  - mission: "/prd"
    pattern: "prd"
    agent: "project-planner"
    importance: 9
    category: "service"
  - mission: "/stories"
    pattern: "stories"
    agent: "project-planner"
    importance: 8
    category: "service"
  - mission: "/sprint"
    pattern: "sprint"
    agent: "project-planner"
    importance: 7
    category: "service"
  - mission: "Execute sprint tasks and implement features"
    pattern: "implement"
    agent: "backend-specialist"
    importance: 6
    category: "worker"
  - mission: "/sprint-closer"
    pattern: "sprint_closer"
    agent: "project-planner"
    importance: 8
    category: "service"
  - mission: "Actualize Wiki and documentation"
    pattern: "docs"
    agent: "analyst"
    importance: 5
    category: "service"')`,
	}
	for _, m := range migrations {
		if _, err := db.Exec(m); err != nil {
			// SQLite returns an error if the column already exists; ignore it
			if !isSQLiteColumnExists(err) {
				log.Printf("Migration warning: %v", err)
			}
		}
	}

	log.Printf("Database initialized at %s", dbPath)
	return &DB{db}, nil
}

func isSQLiteColumnExists(err error) bool {
	return err != nil && (contains(err.Error(), "duplicate column name") ||
		contains(err.Error(), "already exists"))
}

func contains(s, sub string) bool {
	return len(s) >= len(sub) && (s == sub || len(s) > 0 &&
		func() bool {
			for i := 0; i <= len(s)-len(sub); i++ {
				if s[i:i+len(sub)] == sub {
					return true
				}
			}
			return false
		}())
}

// GetSetting retrieves a setting from the database or environment variables.
func (db *DB) GetSetting(key, def string) string {
	var val string
	if err := db.QueryRow("SELECT value FROM settings WHERE key = ?", key).Scan(&val); err == nil && val != "" {
		return val
	}
	// Fallback to environment variables
	envKey := strings.ToUpper(key)
	if envVal := os.Getenv(envKey); envVal != "" {
		return envVal
	}
	return def
}

// SetSetting saves or updates a setting in the database.
func (db *DB) SetSetting(key, value string) error {
	_, err := db.Exec("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", key, value)
	return err
}

// GetDailyUsage counts tasks executed today.
func (db *DB) GetDailyUsage(ctx context.Context) (int, error) {
	var count int
	// We count task_logs from the beginning of the current day (UTC)
	err := db.QueryRowContext(ctx, `
		SELECT COUNT(*) FROM task_logs 
		WHERE executed_at >= date('now', 'start of day')
		AND status NOT IN ('FAILED', 'TRIGGERED') -- Only count those that actually started or finished
	`).Scan(&count)
	return count, err
}
func (db *DB) GetDistinctRepos(ctx context.Context) ([]string, error) {
	rows, err := db.QueryContext(ctx, "SELECT DISTINCT name FROM tasks")
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

func (db *DB) GetUpcomingTaskCountToday(ctx context.Context) (int, error) {
	// This is a simple approximation. In a real system, we'd parse the cron schedules.
	// For now, let's just count all active tasks as a baseline for the forecast.
	var count int
	err := db.QueryRowContext(ctx, "SELECT COUNT(*) FROM tasks WHERE status = 'PENDING'").Scan(&count)
	return count, err
}

// GetDailyLimit retrieves the global daily task limit.
func (db *DB) GetDailyLimit(ctx context.Context) (int, error) {
	valStr := db.GetSetting("daily_task_limit", "0")
	var val int
	fmt.Sscanf(valStr, "%d", &val)
	return val, nil
}

func (db *DB) GetTasksByRepo(ctx context.Context, repoName string) ([]map[string]any, error) {
	rows, err := db.QueryContext(ctx, "SELECT id, name, mission, pattern, agent, schedule, status, importance, category, current_stage, progress FROM tasks WHERE name = ?", repoName)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var tasks []map[string]any
	for rows.Next() {
		var id, name, mission, pattern, agent, schedule, status, category, currentStage string
		var importance, progress int
		if err := rows.Scan(&id, &name, &mission, &pattern, &agent, &schedule, &status, &importance, &category, &currentStage, &progress); err != nil {
			continue
		}
		tasks = append(tasks, map[string]any{
			"id":            id,
			"name":          name,
			"mission":       mission,
			"pattern":       pattern,
			"agent":         agent,
			"schedule":      schedule,
			"status":        status,
			"importance":    importance,
			"category":      category,
			"current_stage": currentStage,
			"progress":      progress,
		})
	}
	return tasks, nil
}

func (db *DB) UpdateTaskProgress(ctx context.Context, taskID string, stage string, progress int) error {
	_, err := db.ExecContext(ctx, "UPDATE tasks SET current_stage = ?, progress = ? WHERE id = ?", stage, progress, taskID)
	return err
}

func (db *DB) AddTaskRunDetail(ctx context.Context, logID int64, phase string, content string, duration int64) error {
	_, err := db.ExecContext(ctx, "INSERT INTO task_run_details (log_id, phase, content, duration_ms) VALUES (?, ?, ?, ?)", logID, phase, content, duration)
	return err
}

func (db *DB) GetTaskRunDetails(ctx context.Context, logID int64) ([]map[string]any, error) {
	rows, err := db.QueryContext(ctx, "SELECT phase, content, duration_ms, created_at FROM task_run_details WHERE log_id = ? ORDER BY id ASC", logID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var details []map[string]any
	for rows.Next() {
		var phase, content, createdAt string
		var duration int64
		if err := rows.Scan(&phase, &content, &duration, &createdAt); err == nil {
			details = append(details, map[string]any{
				"phase":       phase,
				"content":     content,
				"duration_ms": duration,
				"created_at":  createdAt,
			})
		}
	}
	return details, nil
}

func (db *DB) SaveChatMessage(ctx context.Context, role, content, provider, repo string) error {
	_, err := db.ExecContext(ctx, "INSERT INTO web_chat_history (role, content, provider, repo) VALUES (?, ?, ?, ?)", role, content, provider, repo)
	return err
}

func (db *DB) GetChatHistory(ctx context.Context, repo string, limit int) ([]map[string]any, error) {
	query := "SELECT role, content, provider, repo, created_at FROM web_chat_history "
	var args []any
	if repo != "" {
		query += "WHERE repo = ? OR repo = '' "
		args = append(args, repo)
	}
	query += "ORDER BY created_at DESC LIMIT ?"
	args = append(args, limit)

	rows, err := db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var history []map[string]any
	for rows.Next() {
		var role, content, provider, repoName, createdAt string
		if err := rows.Scan(&role, &content, &provider, &repoName, &createdAt); err == nil {
			history = append(history, map[string]any{
				"role":       role,
				"content":    content,
				"provider":   provider,
				"repo":       repoName,
				"created_at": createdAt,
			})
		}
	}
	// Reverse to get chronological order
	for i, j := 0, len(history)-1; i < j; i, j = i+1, j-1 {
		history[i], history[j] = history[j], history[i]
	}
	return history, nil
}
