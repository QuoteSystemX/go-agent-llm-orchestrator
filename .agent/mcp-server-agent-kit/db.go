package main

import (
	"database/sql"
	"fmt"

	_ "github.com/jackc/pgx/v5/stdlib"
)

// DB wraps the standard database/sql connection pool.
type DB struct {
	conn *sql.DB
	dsn  string // retained for tools that need to shell out (e.g. pg_dump for backupS3)
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

	h := &DB{conn: db, dsn: pgURL}
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
		// Tracks which agent identities have already voted on a proposal, as a JSON
		// string array. Added after the table above shipped without it — IF NOT
		// EXISTS makes this safe to re-run against a database that already has the
		// column. Prevents one caller from incrementing `votes` past `required` by
		// calling council_vote multiple times.
		`ALTER TABLE proposals ADD COLUMN IF NOT EXISTS voters TEXT DEFAULT '[]'`,
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
		// Ethics-auditor veto block state, kept separate from `proposals` so that lifting a
		// veto is a pure state transition (see LiftVeto) rather than routed through
		// executeProposal's job-dispatch switch the way "security_fix" is.
		`CREATE TABLE IF NOT EXISTS veto_records (
			id TEXT PRIMARY KEY,
			plan_or_task_ref TEXT,
			status TEXT,
			created_by TEXT,
			lifted_by TEXT,
			reason TEXT,
			proposal_id TEXT,
			created_at TIMESTAMPTZ,
			lifted_at TIMESTAMPTZ
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
