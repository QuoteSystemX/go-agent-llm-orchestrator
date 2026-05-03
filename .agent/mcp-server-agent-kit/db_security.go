package main

import (
	"database/sql"
	"time"
)

func (d *DB) CheckPermission(agent, tool string) (bool, error) {
	var allowed int
	err := d.conn.QueryRow("SELECT allowed FROM permissions WHERE agent_name = ? AND tool_name = ?", agent, tool).Scan(&allowed)
	if err == sql.ErrNoRows {
		// Default: allow if not explicitly restricted (for now)
		return true, nil
	}
	return allowed == 1, err
}

func (d *DB) SetPermission(agent, tool string, allowed bool) error {
	val := 0
	if allowed {
		val = 1
	}
	_, err := d.conn.Exec("INSERT OR REPLACE INTO permissions (agent_name, tool_name, allowed) VALUES (?, ?, ?)", agent, tool, val)
	return err
}

func (d *DB) GetSecret(key string) (string, error) {
	var val string
	err := d.conn.QueryRow("SELECT value FROM secrets WHERE key = ?", key).Scan(&val)
	return val, err
}

func (d *DB) SetSecret(key, value string) error {
	_, err := d.conn.Exec("INSERT OR REPLACE INTO secrets (key, value, updated_at) VALUES (?, ?, ?)", key, value, time.Now())
	return err
}
