package main

import (
	"time"
)

func (d *DB) RecordMetric(tool, agent, project string, duration time.Duration, success bool) error {
	status := "success"
	if !success {
		status = "failure"
	}
	_, err := d.conn.Exec("INSERT INTO metrics (agent_name, tool_name, status, duration_ms, project_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
		agent, tool, status, duration.Milliseconds(), project, time.Now())
	return err
}

func (d *DB) GetMetrics() ([]map[string]any, error) {
	rows, err := d.conn.Query("SELECT tool_name, agent_name, status, duration_ms, created_at FROM metrics ORDER BY created_at DESC LIMIT 100")
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var res []map[string]any
	for rows.Next() {
		var tool, agent, status string
		var duration int64
		var created time.Time
		if err := rows.Scan(&tool, &agent, &status, &duration, &created); err != nil {
			return nil, err
		}
		res = append(res, map[string]any{
			"tool":     tool,
			"agent":    agent,
			"status":   status,
			"duration": duration,
			"created":  created,
		})
	}
	return res, nil
}

func (d *DB) AddWebhook(id, url, events string) error {
	_, err := d.conn.Exec("INSERT OR REPLACE INTO webhooks (id, url, events, created_at) VALUES (?, ?, ?, ?)",
		id, url, events, time.Now())
	return err
}

func (d *DB) GetWebhooks() ([]map[string]string, error) {
	rows, err := d.conn.Query("SELECT id, url, events FROM webhooks")
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var res []map[string]string
	for rows.Next() {
		var id, url, events string
		if err := rows.Scan(&id, &url, &events); err != nil {
			return nil, err
		}
		res = append(res, map[string]string{"id": id, "url": url, "events": events})
	}
	return res, nil
}
func (d *DB) CleanupOldData(days int) error {
	cutoff := time.Now().AddDate(0, 0, -days).Format("2006-01-02 15:04:05")
	
	// Delete old metrics
	_, err := d.conn.Exec("DELETE FROM metrics WHERE created_at < ?", cutoff)
	if err != nil {
		return err
	}
	
	// Delete old completed/failed jobs
	_, err = d.conn.Exec("DELETE FROM jobs WHERE (status = 'completed' OR status = 'failed' OR status = 'cancelled') AND completed_at < ?", cutoff)
	return err
}

func (d *DB) SetSetting(key, value string) error {
	_, err := d.conn.Exec("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", key, value)
	return err
}

func (d *DB) GetSetting(key string, defaultVal string) string {
	var val string
	err := d.conn.QueryRow("SELECT value FROM settings WHERE key = ?", key).Scan(&val)
	if err != nil {
		return defaultVal
	}
	return val
}
