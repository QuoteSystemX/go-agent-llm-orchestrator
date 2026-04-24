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

// GetDailyLimit retrieves the global daily task limit.
func (db *DB) GetDailyLimit(ctx context.Context) (int, error) {
	valStr := db.GetSetting("daily_task_limit", "0")
	var val int
	fmt.Sscanf(valStr, "%d", &val)
	return val, nil
}
