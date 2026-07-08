package main

import (
	"encoding/json"
	"fmt"
	"testing"
	"time"
)

func TestWorkerPool_Execution(t *testing.T) {
	db := newTestDB(t)
	d := NewDispatcher(db, 2)
	d.Start()
	defer d.Stop()

	jobID := "TEST-EXEC-1"
	db.SaveJob(&JobStatus{
		ID:        jobID,
		Name:      "Test Execution",
		Status:    "pending",
		StartedAt: time.Now(),
	})

	err := d.Submit(Task{
		JobID:   jobID,
		Command: "echo",
		Args:    []string{"hello-world"},
	})
	if err != nil {
		t.Fatalf("Submit failed: %v", err)
	}

	// Wait for completion
	timeout := time.After(5 * time.Second)
	tick := time.Tick(100 * time.Millisecond)
	for {
		select {
		case <-timeout:
			t.Fatal("timed out waiting for job completion")
		case <-tick:
			rows, _ := db.conn.Query("SELECT status, message FROM jobs WHERE id = $1", jobID)
			if rows.Next() {
				var status, msg string
				rows.Scan(&status, &msg)
				rows.Close()
				if status == "completed" {
					if msg != "hello-world\n" {
						t.Errorf("expected 'hello-world\n', got %q", msg)
					}
					return
				}
			} else {
				rows.Close()
			}
		}
	}
}

func TestWorkerPool_Recovery(t *testing.T) {
	db := newTestDB(t)

	// 1. Prepare a pending job in DB
	jobID := "RECOVER-ME"
	task := Task{
		JobID:   jobID,
		Command: "echo",
		Args:    []string{"recovered"},
	}
	db.SaveJob(&JobStatus{
		ID:     jobID,
		Status: "pending",
	})
	d1 := NewDispatcher(db, 1)
	d1.Submit(task) // This saves task_data
	// We don't start d1, just use it to save data, or start and stop immediately

	// 2. Start a NEW dispatcher and check if it picks up the job
	d2 := NewDispatcher(db, 1)
	d2.Start()
	defer d2.Stop()

	timeout := time.After(5 * time.Second)
	tick := time.Tick(200 * time.Millisecond)
	for {
		select {
		case <-timeout:
			t.Fatal("timed out waiting for job recovery")
		case <-tick:
			var status string
			db.conn.QueryRow("SELECT status FROM jobs WHERE id = $1", jobID).Scan(&status)
			if status == "completed" {
				return
			}
		}
	}
}

func TestWorkerPool_Concurrency(t *testing.T) {
	db := newTestDB(t)

	// Only 1 worker
	d := NewDispatcher(db, 1)
	d.Start()
	defer d.Stop()

	// Submit 2 long jobs
	for i := 1; i <= 2; i++ {
		id := fmt.Sprintf("LONG-%d", i)
		db.SaveJob(&JobStatus{ID: id, Status: "pending"})
		d.Submit(Task{
			JobID:   id,
			Command: "sleep",
			Args:    []string{"2"},
		})
	}

	// Check that only 1 is running (at most)
	success := false
	for i := 0; i < 10; i++ {
		time.Sleep(200 * time.Millisecond)
		var runningCount int
		db.conn.QueryRow("SELECT COUNT(*) FROM jobs WHERE status = 'running'").Scan(&runningCount)
		if runningCount == 1 {
			success = true
			break
		}
	}

	if !success {
		t.Errorf("expected 1 running job during execution peak")
	}
}

func TestDispatcher_StopDuringRecovery(t *testing.T) {
	db := newTestDB(t)

	// Seed pending jobs with task_data so recoverJobs has work to do.
	const n = 50
	for i := 0; i < n; i++ {
		jobID := fmt.Sprintf("RECOVER-STOP-%d", i)
		task := Task{
			JobID:   jobID,
			Command: "echo",
			Args:    []string{"recovered"},
		}
		data, err := json.Marshal(task)
		if err != nil {
			t.Fatalf("failed to marshal task: %v", err)
		}
		_, err = db.conn.Exec(
			"INSERT INTO jobs (id, status, task_data) VALUES ($1, 'pending', $2)",
			jobID, string(data),
		)
		if err != nil {
			t.Fatalf("failed to insert pending job: %v", err)
		}
	}

	// Start the dispatcher and immediately stop it. Before the fix this
	// could panic with "send on closed channel" if recoverJobs was still
	// iterating over pending jobs while Stop closed the job queue.
	d := NewDispatcher(db, 2)
	d.Start()
	time.Sleep(5 * time.Millisecond)
	d.Stop()
}
