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
	main    *sql.DB
	history *sql.DB
}

// Main returns the main database handle (configuration)
func (db *DB) Main() *sql.DB { return db.main }

// History returns the history database handle (logs)
func (db *DB) History() *sql.DB { return db.history }

// Proxy methods for compatibility (target main db)
func (db *DB) QueryContext(ctx context.Context, query string, args ...any) (*sql.Rows, error) {
	return db.main.QueryContext(ctx, query, args...)
}
func (db *DB) ExecContext(ctx context.Context, query string, args ...any) (sql.Result, error) {
	return db.main.ExecContext(ctx, query, args...)
}
func (db *DB) QueryRowContext(ctx context.Context, query string, args ...any) *sql.Row {
	return db.main.QueryRowContext(ctx, query, args...)
}
func (db *DB) QueryRow(query string, args ...any) *sql.Row {
	return db.main.QueryRow(query, args...)
}
func (db *DB) Exec(query string, args ...any) (sql.Result, error) {
	return db.main.Exec(query, args...)
}
func (db *DB) Begin() (*sql.Tx, error) {
	return db.main.Begin()
}
func (db *DB) BeginTx(ctx context.Context, opts *sql.TxOptions) (*sql.Tx, error) {
	return db.main.BeginTx(ctx, opts)
}
func (db *DB) Query(query string, args ...any) (*sql.Rows, error) {
	return db.main.Query(query, args...)
}
func (db *DB) Ping() error {
	return db.main.Ping()
}
func (db *DB) Stats() sql.DBStats {
	return db.main.Stats()
}

// InitDB initializes the SQLite databases at the given paths
func InitDB(dbPath string) (*DB, error) {
	// Ensure directory exists
	dir := filepath.Dir(dbPath)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return nil, fmt.Errorf("creating db directory: %w", err)
	}

	historyPath := filepath.Join(dir, "history.db")

	main, err := sql.Open("sqlite", dbPath)
	if err != nil {
		return nil, fmt.Errorf("opening main db: %w", err)
	}

	history, err := sql.Open("sqlite", historyPath)
	if err != nil {
		return nil, fmt.Errorf("opening history db: %w", err)
	}

	setupConn := func(db *sql.DB) error {
		// Single connection ensures PRAGMA busy_timeout applies to every query.
		// SQLite allows only one writer at a time regardless of pool size, so
		// queuing at the connection-pool level is equivalent and avoids SQLITE_BUSY.
		db.SetMaxOpenConns(1)
		db.SetMaxIdleConns(1)
		db.SetConnMaxLifetime(0)
		if _, err := db.Exec("PRAGMA journal_mode=WAL;"); err != nil {
			return err
		}
		if _, err := db.Exec("PRAGMA busy_timeout=60000;"); err != nil {
			return err
		}
		if _, err := db.Exec("PRAGMA synchronous=NORMAL;"); err != nil {
			return err
		}
		if _, err := db.Exec("PRAGMA cache_size=-2000;"); err != nil {
			return err
		}
		if _, err := db.Exec("PRAGMA mmap_size=268435456;"); err != nil {
			return err
		}
		return nil
	}

	if err := setupConn(main); err != nil {
		return nil, fmt.Errorf("setting up main db: %w", err)
	}
	if err := setupConn(history); err != nil {
		return nil, fmt.Errorf("setting up history db: %w", err)
	}

	// Initialize Main Schema
	mainSchema := `
	CREATE TABLE IF NOT EXISTS tasks (
		id TEXT PRIMARY KEY,
		name TEXT NOT NULL,
		agent TEXT DEFAULT '',
		mission TEXT,
		pattern TEXT,
		schedule TEXT NOT NULL,
		status TEXT NOT NULL,
		current_stage TEXT DEFAULT 'idle',
		progress INTEGER DEFAULT 0,
		last_run_at DATETIME,
		approval_required INTEGER DEFAULT 0,
		pending_decision TEXT DEFAULT '',
		failure_count INTEGER DEFAULT 0,
		importance INTEGER DEFAULT 1,
		category TEXT DEFAULT 'worker',
		auto_paused INTEGER DEFAULT 0,
		last_error TEXT,
		max_retries INTEGER DEFAULT 3,
		current_retry INTEGER DEFAULT 0,
		created_at DATETIME DEFAULT CURRENT_TIMESTAMP
	);
	CREATE TABLE IF NOT EXISTS sessions (
		id TEXT PRIMARY KEY,
		task_id TEXT,
		jules_session_id TEXT UNIQUE,
		status TEXT NOT NULL,
		last_context_hash TEXT,
		updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
	);
	CREATE TABLE IF NOT EXISTS settings (
		key TEXT PRIMARY KEY,
		value TEXT
	);
	CREATE TABLE IF NOT EXISTS templates (
		name TEXT PRIMARY KEY,
		content TEXT NOT NULL,
		updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
	);
	CREATE TABLE IF NOT EXISTS budgets (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		target_type TEXT NOT NULL,
		target_id TEXT,
		daily_session_limit INTEGER DEFAULT 100,
		monthly_cost_limit REAL DEFAULT 50.0,
		alert_threshold REAL DEFAULT 0.8,
		created_at DATETIME DEFAULT CURRENT_TIMESTAMP
	);
	CREATE TABLE IF NOT EXISTS schema_migrations (
		version INTEGER PRIMARY KEY
	);
	CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
	`
	if _, err := main.Exec(mainSchema); err != nil {
		return nil, fmt.Errorf("init main schema: %w", err)
	}

	// Runtime migrations for existing databases
	if err := runMigrations(main, []string{
		"ALTER TABLE tasks ADD COLUMN auto_paused INTEGER DEFAULT 0",
		"ALTER TABLE tasks ADD COLUMN importance INTEGER DEFAULT 1",
		"ALTER TABLE tasks ADD COLUMN category TEXT DEFAULT 'worker'",
		"ALTER TABLE tasks ADD COLUMN last_error TEXT",
		"ALTER TABLE tasks ADD COLUMN max_retries INTEGER DEFAULT 3",
		"ALTER TABLE tasks ADD COLUMN current_retry INTEGER DEFAULT 0",
	}); err != nil {
		log.Printf("Main DB migrations failed: %v", err)
	}

	// Initialize History Schema
	historySchema := `
	CREATE TABLE IF NOT EXISTS task_logs (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		task_id TEXT NOT NULL,
		session_id TEXT,
		jules_session_id TEXT,
		executed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
		input_data TEXT,
		output_data TEXT,
		status TEXT,
		error TEXT,
		duration_ms INTEGER,
		prompt_tokens INTEGER DEFAULT 0,
		completion_tokens INTEGER DEFAULT 0,
		total_tokens INTEGER DEFAULT 0,
		cost_usd REAL DEFAULT 0.0
	);
	CREATE TABLE IF NOT EXISTS task_run_details (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		log_id INTEGER NOT NULL,
		phase TEXT NOT NULL,
		content TEXT,
		duration_ms INTEGER DEFAULT 0,
		created_at DATETIME DEFAULT CURRENT_TIMESTAMP
	);
	CREATE TABLE IF NOT EXISTS audit_logs (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		session_id TEXT,
		action TEXT,
		details TEXT,
		created_at DATETIME DEFAULT CURRENT_TIMESTAMP
	);
	CREATE TABLE IF NOT EXISTS web_chat_history (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		role TEXT NOT NULL,
		content TEXT NOT NULL,
		provider TEXT,
		repo TEXT,
		created_at DATETIME DEFAULT CURRENT_TIMESTAMP
	);
	CREATE INDEX IF NOT EXISTS idx_task_logs_task_id ON task_logs(task_id);
	CREATE INDEX IF NOT EXISTS idx_task_run_details_log_id ON task_run_details(log_id);
	CREATE INDEX IF NOT EXISTS idx_chat_history_repo ON web_chat_history(repo);
	`
	if _, err := history.Exec(historySchema); err != nil {
		return nil, fmt.Errorf("init history schema: %w", err)
	}

	// History DB migrations
	if _, err := history.Exec("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY)"); err != nil {
		return nil, fmt.Errorf("init history migrations table: %w", err)
	}

	if err := runMigrations(history, []string{
		"ALTER TABLE task_logs ADD COLUMN jules_session_id TEXT",
		"ALTER TABLE task_logs ADD COLUMN prompt_tokens INTEGER DEFAULT 0",
		"ALTER TABLE task_logs ADD COLUMN completion_tokens INTEGER DEFAULT 0",
		"ALTER TABLE task_logs ADD COLUMN total_tokens INTEGER DEFAULT 0",
		"ALTER TABLE task_logs ADD COLUMN cost_usd REAL DEFAULT 0.0",
	}); err != nil {
		log.Printf("History DB migrations failed: %v", err)
	}

	log.Printf("Databases initialized: main and history")
	return &DB{main: main, history: history}, nil
}

func runMigrations(db *sql.DB, queries []string) error {
	for i, q := range queries {
		version := i + 1
		var exists int
		err := db.QueryRow("SELECT COUNT(*) FROM schema_migrations WHERE version = ?", version).Scan(&exists)
		if err == nil && exists > 0 {
			continue
		}

		log.Printf("Applying migration version %d: %s", version, q)
		tx, err := db.Begin()
		if err != nil {
			return err
		}

		if _, err := tx.Exec(q); err != nil {
			// If it's a duplicate column error, we still mark it as migrated
			if !strings.Contains(err.Error(), "duplicate column") {
				tx.Rollback()
				return fmt.Errorf("migration %d failed: %w", version, err)
			}
		}

		if _, err := tx.Exec("INSERT INTO schema_migrations (version) VALUES (?)", version); err != nil {
			tx.Rollback()
			return fmt.Errorf("failed to record migration %d: %w", version, err)
		}

		if err := tx.Commit(); err != nil {
			return err
		}
	}
	return nil
}

// Close closes both database connections
func (db *DB) Close() error {
	err1 := db.main.Close()
	err2 := db.history.Close()
	if err1 != nil {
		return err1
	}
	return err2
}

// GetSetting retrieves a setting from the main database or environment variables.
func (db *DB) GetSetting(key, def string) string {
	var val string
	if err := db.main.QueryRow("SELECT value FROM settings WHERE key = ?", key).Scan(&val); err == nil && val != "" {
		return val
	}
	// Fallback to environment variables
	envKey := strings.ToUpper(key)
	if envVal := os.Getenv(envKey); envVal != "" {
		return envVal
	}
	return def
}

// SetSetting saves or updates a setting in the main database.
func (db *DB) SetSetting(key, value string) error {
	_, err := db.main.Exec("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", key, value)
	return err
}

// GetDailyUsage counts tasks executed today.
func (db *DB) GetDailyUsage(ctx context.Context) (int, error) {
	var count int
	// We count task_logs from the beginning of the current day (UTC)
	err := db.history.QueryRowContext(ctx, `
		SELECT COUNT(*) FROM task_logs
		WHERE executed_at >= date('now', 'start of day')
		AND status != 'TRIGGERED'
	`).Scan(&count)
	return count, err
}
func (db *DB) GetDistinctRepos(ctx context.Context) ([]string, error) {
	rows, err := db.main.QueryContext(ctx, "SELECT DISTINCT name FROM tasks")
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
	var count int
	err := db.main.QueryRowContext(ctx, "SELECT COUNT(*) FROM tasks WHERE status = 'PENDING'").Scan(&count)
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
	rows, err := db.main.QueryContext(ctx, "SELECT id, name, mission, pattern, agent, schedule, status, importance, category, current_stage, progress FROM tasks WHERE name = ?", repoName)
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
	_, err := db.main.ExecContext(ctx, "UPDATE tasks SET current_stage = ?, progress = ? WHERE id = ?", stage, progress, taskID)
	return err
}

func (db *DB) AddTaskRunDetail(ctx context.Context, logID int64, phase string, content string, duration int64) (int64, error) {
	res, err := db.history.ExecContext(ctx, "INSERT INTO task_run_details (log_id, phase, content, duration_ms) VALUES (?, ?, ?, ?)", logID, phase, content, duration)
	if err != nil {
		return 0, err
	}
	return res.LastInsertId()
}

func (db *DB) UpdateTaskRunDetailContent(ctx context.Context, id int64, content string) error {
	_, err := db.history.ExecContext(ctx, "UPDATE task_run_details SET content = ? WHERE id = ?", content, id)
	return err
}

func (db *DB) GetTaskRunDetails(ctx context.Context, logID int64) ([]map[string]any, error) {
	rows, err := db.history.QueryContext(ctx, "SELECT phase, content, duration_ms, created_at FROM task_run_details WHERE log_id = ? ORDER BY id ASC", logID)
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
	_, err := db.history.ExecContext(ctx, "INSERT INTO web_chat_history (role, content, provider, repo) VALUES (?, ?, ?, ?)", role, content, provider, repo)
	return err
}

func (db *DB) ClearChatHistory(ctx context.Context, repo string) error {
	var err error
	if repo != "" {
		_, err = db.history.ExecContext(ctx, "DELETE FROM web_chat_history WHERE repo = ? OR repo = ''", repo)
	} else {
		_, err = db.history.ExecContext(ctx, "DELETE FROM web_chat_history")
	}
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

	rows, err := db.history.QueryContext(ctx, query, args...)
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
