package main

import (
	"database/sql"
	"time"
)

func (d *DB) CheckPermission(agent, tool string) (bool, error) {
	var allowed bool
	err := d.conn.QueryRow("SELECT allowed FROM permissions WHERE agent_name = $1 AND tool_name = $2", agent, tool).Scan(&allowed)
	if err == sql.ErrNoRows {
		return true, nil
	}
	return allowed, err
}

func (d *DB) SetPermission(agent, tool string, allowed bool) error {
	_, err := d.conn.Exec(
		`INSERT INTO permissions (agent_name, tool_name, allowed)
		 VALUES ($1, $2, $3)
		 ON CONFLICT (agent_name, tool_name) DO UPDATE SET allowed=EXCLUDED.allowed`,
		agent, tool, allowed,
	)
	return err
}

func (d *DB) GetSecret(key string) (string, error) {
	var val string
	err := d.conn.QueryRow("SELECT value FROM secrets WHERE key = $1", key).Scan(&val)
	return val, err
}

func (d *DB) SetSecret(key, value string) error {
	_, err := d.conn.Exec(
		`INSERT INTO secrets (key, value, updated_at)
		 VALUES ($1, $2, $3)
		 ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=EXCLUDED.updated_at`,
		key, value, time.Now(),
	)
	return err
}
