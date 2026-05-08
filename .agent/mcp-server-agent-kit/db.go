package main

import (
	"database/sql"
	"fmt"
	"path/filepath"

	_ "modernc.org/sqlite"
)

type DB struct {
	conn        *sql.DB
	connSearch  *sql.DB
	connMetrics *sql.DB
}

func InitDB(projectRoot string, mainDBPathOverride string) (*DB, error) {
	dbPath := mainDBPathOverride
	if dbPath == "" {
		dbPath = filepath.Join(projectRoot, ".agent", "mcp_main.db")
	}
	dbDir := filepath.Dir(dbPath)
	searchPath := filepath.Join(dbDir, "mcp_search.db")
	metricsPath := filepath.Join(dbDir, "mcp_metrics.db")

	initConn := func(path string) (*sql.DB, error) {
		dsn := fmt.Sprintf("%s?_busy_timeout=10000&_journal_mode=WAL&_sync=NORMAL", path)
		db, err := sql.Open("sqlite", dsn)
		if err != nil {
			return nil, err
		}
		db.SetMaxOpenConns(10) // Allow some concurrency for readers
		return db, nil
	}

	mainDB, err := initConn(dbPath)
	if err != nil {
		return nil, err
	}
	searchDB, err := initConn(searchPath)
	if err != nil {
		return nil, err
	}
	metricsDB, err := initConn(metricsPath)
	if err != nil {
		return nil, err
	}

	h := &DB{
		conn:        mainDB,
		connSearch:  searchDB,
		connMetrics: metricsDB,
	}

	// Migrations
	mainQueries := []string{
		`CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, name TEXT, status TEXT, progress INTEGER, message TEXT, started_at DATETIME, completed_at DATETIME, command TEXT, task_data TEXT);`,
		`CREATE TABLE IF NOT EXISTS proposals (id TEXT PRIMARY KEY, title TEXT, proposer TEXT, votes INTEGER, required INTEGER, status TEXT, created_at DATETIME, command_type TEXT, command_data TEXT);`,
		`CREATE TABLE IF NOT EXISTS permissions (agent_name TEXT, tool_name TEXT, allowed INTEGER, PRIMARY KEY (agent_name, tool_name));`,
		`CREATE TABLE IF NOT EXISTS secrets (key TEXT PRIMARY KEY, value TEXT, updated_at DATETIME);`,
		`CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, name TEXT, path TEXT, created_at DATETIME);`,
		`CREATE TABLE IF NOT EXISTS webhooks (id TEXT PRIMARY KEY, url TEXT, events TEXT, created_at DATETIME);`,
		`CREATE TABLE IF NOT EXISTS resource_hooks (resource_uri TEXT, event_type TEXT, script_path TEXT, PRIMARY KEY (resource_uri, event_type));`,
		`CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);`,
	}

	for _, q := range mainQueries {
		if _, err := h.conn.Exec(q); err != nil {
			return nil, fmt.Errorf("main migration error: %v", err)
		}
	}

	searchQueries := []string{
		`CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(path UNINDEXED, content, type UNINDEXED, tokenize='porter');`,
	}
	for _, q := range searchQueries {
		if _, err := h.connSearch.Exec(q); err != nil {
			return nil, fmt.Errorf("search migration error: %v", err)
		}
	}

	metricsQueries := []string{
		`CREATE TABLE IF NOT EXISTS metrics (id INTEGER PRIMARY KEY AUTOINCREMENT, agent_name TEXT, tool_name TEXT, duration_ms INTEGER, status TEXT, project_id TEXT, created_at DATETIME);`,
	}
	for _, q := range metricsQueries {
		if _, err := h.connMetrics.Exec(q); err != nil {
			return nil, fmt.Errorf("metrics migration error: %v", err)
		}
	}

	return h, nil
}
