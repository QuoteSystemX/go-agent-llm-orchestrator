package main

import (
	"database/sql"
	"fmt"

	_ "github.com/jackc/pgx/v5/stdlib"
)

// DB wraps the standard database/sql connection pool.
type DB struct {
	conn *sql.DB
}

// InitDB initializes a connection to the PostgreSQL database and runs migrations.
//
// Parameters:
//   - pgURL: the PostgreSQL connection string (must not be empty).
//
// Returns:
//   - *DB: a pointer to the initialized DB wrapper.
//   - error: an error if the connection fails or migrations cannot be applied.
func InitDB(pgURL string) (*DB, error) {
	if pgURL == "" {
		return nil, fmt.Errorf("database URL is required (--pg-url or DATABASE_URL)")
	}

	db, err := sql.Open("pgx", pgURL)
	if err != nil {
		return nil, fmt.Errorf("open db: %w", err)
	}
	db.SetMaxOpenConns(25)
	db.SetMaxIdleConns(5)

	h := &DB{conn: db}
	if err := h.migrate(); err != nil {
		_ = db.Close()
		return nil, fmt.Errorf("migration: %w", err)
	}

	return h, nil
}

// migrate creates the necessary database schema if it doesn't already exist.
//
// Returns:
//   - error: an error if the table creation statements fail.
func (d *DB) migrate() error {
	stmts := []string{
		`CREATE TABLE IF NOT EXISTS jobs (
			id TEXT PRIMARY KEY,
			name TEXT,
			status TEXT,
			progress INTEGER,
			message TEXT,
			started_at TIMESTAMPTZ,
			completed_at TIMESTAMPTZ,
			command TEXT,
			task_data TEXT
		)`,
		`CREATE TABLE IF NOT EXISTS proposals (
			id TEXT PRIMARY KEY,
			title TEXT,
			proposer TEXT,
			votes INTEGER,
			required INTEGER,
			status TEXT,
			created_at TIMESTAMPTZ,
			command_type TEXT,
			command_data TEXT
		)`,
		`CREATE TABLE IF NOT EXISTS permissions (
			agent_name TEXT,
			tool_name TEXT,
			allowed BOOLEAN,
			PRIMARY KEY (agent_name, tool_name)
		)`,
		`CREATE TABLE IF NOT EXISTS secrets (
			key TEXT PRIMARY KEY,
			value TEXT,
			updated_at TIMESTAMPTZ
		)`,
		`CREATE TABLE IF NOT EXISTS projects (
			id TEXT PRIMARY KEY,
			name TEXT,
			path TEXT,
			created_at TIMESTAMPTZ
		)`,
		`CREATE TABLE IF NOT EXISTS webhooks (
			id TEXT PRIMARY KEY,
			url TEXT,
			events TEXT,
			created_at TIMESTAMPTZ
		)`,
		`CREATE TABLE IF NOT EXISTS resource_hooks (
			resource_uri TEXT,
			event_type TEXT,
			script_path TEXT,
			PRIMARY KEY (resource_uri, event_type)
		)`,
		`CREATE TABLE IF NOT EXISTS settings (
			key TEXT PRIMARY KEY,
			value TEXT
		)`,
		`CREATE TABLE IF NOT EXISTS metrics (
			id BIGSERIAL PRIMARY KEY,
			agent_name TEXT,
			tool_name TEXT,
			duration_ms INTEGER,
			status TEXT,
			project_id TEXT,
			created_at TIMESTAMPTZ
		)`,
		`CREATE TABLE IF NOT EXISTS documents (
			path TEXT PRIMARY KEY,
			content TEXT,
			type TEXT
		)`,
		`CREATE INDEX IF NOT EXISTS documents_tsv_idx ON documents USING GIN (to_tsvector('english', coalesce(content,'')))`,
	}

	for _, q := range stmts {
		if _, err := d.conn.Exec(q); err != nil {
			return fmt.Errorf("%w", err)
		}
	}
	return nil
}
