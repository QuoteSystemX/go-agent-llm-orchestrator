package main

import (
	"time"
)

func (d *DB) SaveJob(j *JobStatus) error {
	_, err := d.conn.Exec(
		"INSERT OR REPLACE INTO jobs (id, name, status, progress, message, started_at) VALUES (?, ?, ?, ?, ?, ?)",
		j.ID, j.Name, j.Status, j.Progress, j.Message, j.StartedAt,
	)
	return err
}

func (d *DB) GetJobs() ([]*JobStatus, error) {
	rows, err := d.conn.Query("SELECT id, name, status, progress, message, started_at FROM jobs ORDER BY started_at DESC")
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var jobs []*JobStatus
	for rows.Next() {
		j := &JobStatus{}
		if err := rows.Scan(&j.ID, &j.Name, &j.Status, &j.Progress, &j.Message, &j.StartedAt); err != nil {
			return nil, err
		}
		jobs = append(jobs, j)
	}
	return jobs, nil
}

func (d *DB) RegisterProject(id, name, path string) error {
	_, err := d.conn.Exec("INSERT OR REPLACE INTO projects (id, name, path, created_at) VALUES (?, ?, ?, ?)", id, name, path, time.Now())
	return err
}

func (d *DB) GetProjects() (map[string]string, error) {
	rows, err := d.conn.Query("SELECT id, path FROM projects")
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	projects := make(map[string]string)
	for rows.Next() {
		var id, path string
		if err := rows.Scan(&id, &path); err != nil {
			return nil, err
		}
		projects[id] = path
	}
	return projects, nil
}
