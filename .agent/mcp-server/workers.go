package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"sync"
	"time"
)

type Task struct {
	JobID   string   `json:"jobId"`
	Command string   `json:"command"`
	Args    []string `json:"args"`
	Dir     string   `json:"dir"`
	Env     []string `json:"env"`
}

type Dispatcher struct {
	jobQueue   chan Task
	maxWorkers int
	db         *DB
	wg         sync.WaitGroup
	ctx        context.Context
	cancel     context.CancelFunc
}

func NewDispatcher(db *DB, maxWorkers int) *Dispatcher {
	ctx, cancel := context.WithCancel(context.Background())
	return &Dispatcher{
		jobQueue:   make(chan Task, 100),
		maxWorkers: maxWorkers,
		db:         db,
		ctx:        ctx,
		cancel:     cancel,
	}
}

func (d *Dispatcher) Start() {
	for i := 0; i < d.maxWorkers; i++ {
		d.wg.Add(1)
		go d.worker(i)
	}
	// Recovery: Resume pending jobs from DB
	go d.recoverJobs()
}

func (d *Dispatcher) Stop() {
	d.cancel()
	close(d.jobQueue)
	d.wg.Wait()
}

func (d *Dispatcher) Submit(t Task) error {
	// Serialize task for recovery
	data, err := json.Marshal(t)
	if err != nil {
		return err
	}
	
	// Update DB with task data
	_, err = d.db.conn.Exec("UPDATE jobs SET task_data = ? WHERE id = ?", string(data), t.JobID)
	if err != nil {
		return err
	}

	select {
	case d.jobQueue <- t:
		return nil
	default:
		return fmt.Errorf("job queue is full")
	}
}

func (d *Dispatcher) worker(id int) {
	defer d.wg.Done()
	fmt.Fprintf(os.Stderr, "Worker %d started\n", id)
	
	for {
		select {
		case <-d.ctx.Done():
			fmt.Fprintf(os.Stderr, "Worker %d stopping...\n", id)
			return
		case t, ok := <-d.jobQueue:
			if !ok {
				return
			}
			d.execute(id, t)
		}
	}
}

func (d *Dispatcher) execute(workerID int, t Task) {
	// Update status to running
	d.db.conn.Exec("UPDATE jobs SET status = ?, message = ?, started_at = ? WHERE id = ?", 
		"running", fmt.Sprintf("Started by worker %d", workerID), time.Now(), t.JobID)

	cmd := exec.CommandContext(d.ctx, t.Command, t.Args...)
	cmd.Dir = t.Dir
	if len(t.Env) > 0 {
		cmd.Env = append(os.Environ(), t.Env...)
	} else {
		cmd.Env = os.Environ()
	}
	
	output, err := cmd.CombinedOutput()

	status := "completed"
	msg := string(output)
	if err != nil {
		if d.ctx.Err() != nil {
			status = "cancelled"
			msg = "Job cancelled by server shutdown"
		} else {
			status = "failed"
			msg = fmt.Sprintf("Error: %v\n\nOutput:\n%s", err, msg)
		}
	}

	d.db.conn.Exec("UPDATE jobs SET status = ?, message = ?, progress = 100, completed_at = ? WHERE id = ?", 
		status, msg, time.Now(), t.JobID)
}

func (d *Dispatcher) recoverJobs() {
	// Find jobs that are not completed/failed/cancelled
	rows, err := d.db.conn.Query("SELECT id, task_data FROM jobs WHERE status IN ('pending', 'running') AND task_data IS NOT NULL")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Recovery error: %v\n", err)
		return
	}
	defer rows.Close()

	for rows.Next() {
		var id, taskData string
		if err := rows.Scan(&id, &taskData); err != nil {
			continue
		}
		
		var t Task
		if err := json.Unmarshal([]byte(taskData), &t); err != nil {
			fmt.Fprintf(os.Stderr, "Failed to unmarshal task %s: %v\n", id, err)
			continue
		}
		
		fmt.Fprintf(os.Stderr, "Recovering job %s...\n", id)
		d.jobQueue <- t
	}
}
