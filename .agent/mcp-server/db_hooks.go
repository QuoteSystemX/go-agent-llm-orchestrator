package main

type ResourceHook struct {
	ResourceURI string `json:"resource_uri"`
	EventType   string `json:"event_type"` // on_read, on_change
	ScriptPath  string `json:"script_path"`
}

func (d *DB) AddHook(uri, event, script string) error {
	_, err := d.conn.Exec("INSERT OR REPLACE INTO resource_hooks (resource_uri, event_type, script_path) VALUES (?, ?, ?)",
		uri, event, script)
	return err
}

func (d *DB) RemoveHook(uri, event string) error {
	_, err := d.conn.Exec("DELETE FROM resource_hooks WHERE resource_uri = ? AND event_type = ?", uri, event)
	return err
}

func (d *DB) GetHooks() ([]ResourceHook, error) {
	rows, err := d.conn.Query("SELECT resource_uri, event_type, script_path FROM resource_hooks")
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var hooks []ResourceHook
	for rows.Next() {
		var h ResourceHook
		if err := rows.Scan(&h.ResourceURI, &h.EventType, &h.ScriptPath); err != nil {
			return nil, err
		}
		hooks = append(hooks, h)
	}
	return hooks, nil
}

func (d *DB) GetHooksForResource(uri, event string) ([]ResourceHook, error) {
	rows, err := d.conn.Query("SELECT resource_uri, event_type, script_path FROM resource_hooks WHERE (resource_uri = ? OR resource_uri = '*') AND event_type = ?", uri, event)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var hooks []ResourceHook
	for rows.Next() {
		var h ResourceHook
		if err := rows.Scan(&h.ResourceURI, &h.EventType, &h.ScriptPath); err != nil {
			return nil, err
		}
		hooks = append(hooks, h)
	}
	return hooks, nil
}
