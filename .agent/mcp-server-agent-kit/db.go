package main

import (
	"database/sql"
	"fmt"

	_ "modernc.org/sqlite"
)

type DB struct {
	conn *sql.DB
}

func InitDB(path string) (*DB, error) {
	db, err := sql.Open("sqlite", path)
	if err != nil {
		return nil, err
	}

	if err := db.Ping(); err != nil {
		return nil, err
	}

	// Enable WAL mode for better concurrency
	db.Exec("PRAGMA journal_mode=WAL;")

	queries := []string{
		`CREATE TABLE IF NOT EXISTS jobs (
			id TEXT PRIMARY KEY,
			name TEXT,
			status TEXT,
			progress INTEGER,
			message TEXT,
			started_at DATETIME,
			completed_at DATETIME,
			command TEXT,
			task_data TEXT
		);`,
		`CREATE TABLE IF NOT EXISTS proposals (
			id TEXT PRIMARY KEY,
			title TEXT,
			proposer TEXT,
			votes INTEGER,
			required INTEGER,
			status TEXT,
			created_at DATETIME,
			command_type TEXT,
			command_data TEXT
		);`,
		`CREATE TABLE IF NOT EXISTS permissions (
			agent_name TEXT,
			tool_name TEXT,
			allowed INTEGER,
			PRIMARY KEY (agent_name, tool_name)
		);`,
		`CREATE TABLE IF NOT EXISTS secrets (
			key TEXT PRIMARY KEY,
			value TEXT,
			updated_at DATETIME
		);`,
		`CREATE TABLE IF NOT EXISTS projects (
			id TEXT PRIMARY KEY,
			name TEXT,
			path TEXT,
			created_at DATETIME
		);`,
		`CREATE TABLE IF NOT EXISTS webhooks (
			id TEXT PRIMARY KEY,
			url TEXT,
			events TEXT,
			created_at DATETIME
		);`,
		`CREATE TABLE IF NOT EXISTS metrics (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			agent_name TEXT,
			tool_name TEXT,
			duration_ms INTEGER,
			status TEXT,
			project_id TEXT,
			created_at DATETIME
		);`,
		`CREATE TABLE IF NOT EXISTS resource_hooks (
			resource_uri TEXT,
			event_type TEXT,
			script_path TEXT,
			PRIMARY KEY (resource_uri, event_type)
		);`,
		`CREATE TABLE IF NOT EXISTS settings (
			key TEXT PRIMARY KEY,
			value TEXT
		);`,
		`CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
			path UNINDEXED, 
			content,
			type UNINDEXED,
			tokenize='porter'
		);`,
	}

	for _, q := range queries {
		if _, err := db.Exec(q); err != nil {
			return nil, fmt.Errorf("migration error: %v", err)
		}
	}

	return &DB{conn: db}, nil
}
