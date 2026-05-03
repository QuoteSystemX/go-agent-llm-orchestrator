package main

import (
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestResourceHooks_OnChange(t *testing.T) {
	db, cleanup := setupTestDB(t)
	defer cleanup()

	tempDir, err := os.MkdirTemp("", "hooks-test")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(tempDir)

	d := NewDispatcher(db, 1)
	d.Start()
	defer d.Stop()

	// Create docs dir first so Watch can add it
	docsDir := filepath.Join(tempDir, "docs")
	os.MkdirAll(docsDir, 0755)

	idx, _ := NewIndexer(db, tempDir, []string{"docs"}, d)
	go idx.Watch()
	time.Sleep(100 * time.Millisecond) // Give it time to start watching

	// Register hook
	relPath := "docs/trigger.md"
	script := "echo"
	db.AddHook(relPath, "on_change", script)

	// Create/Modify file
	fullPath := filepath.Join(tempDir, relPath)
	t.Logf("Writing to %s", fullPath)
	os.WriteFile(fullPath, []byte("change me"), 0644)

	// Wait for hook to trigger and job to be created
	success := false
	timeout := time.After(10 * time.Second)
	tick := time.Tick(500 * time.Millisecond)
	for {
		select {
		case <-timeout:
			t.Fatal("timed out waiting for hook trigger")
		case <-tick:
			var count int
			db.conn.QueryRow("SELECT COUNT(*) FROM jobs WHERE id LIKE 'HOOK-%'").Scan(&count)
			t.Logf("Current HOOK job count: %d", count)
			if count > 0 {
				success = true
				goto End
			}
		}
	}
End:
	if !success {
		t.Error("Hook was not triggered or job not recorded")
	}
}

func TestResourceHooks_OnRead(t *testing.T) {
	db, cleanup := setupTestDB(t)
	defer cleanup()

	tempDir, err := os.MkdirTemp("", "hooks-read-test")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(tempDir)

	d := NewDispatcher(db, 1)
	d.Start()
	defer d.Stop()

	idx, _ := NewIndexer(db, tempDir, []string{"wiki"}, d)
	h := &handler{
		projectRoot: tempDir,
		db:          db,
		dispatcher:  d,
		indexer:     idx,
	}

	// Register hook
	relPath := "wiki/ARCHITECTURE.md"
	db.AddHook(relPath, "on_read", "echo")

	// Create file
	fullPath := filepath.Join(tempDir, relPath)
	os.MkdirAll(filepath.Dir(fullPath), 0755)
	os.WriteFile(fullPath, []byte("# Arch"), 0644)

	// Call loadItem which triggers on_read
	_, err = h.loadItem(fullPath)
	if err != nil {
		t.Fatalf("loadItem failed: %v", err)
	}

	// Verify job created
	var count int
	err = db.conn.QueryRow("SELECT COUNT(*) FROM jobs WHERE id LIKE 'READ-HOOK-%'").Scan(&count)
	if err != nil {
		t.Fatal(err)
	}

	if count == 0 {
		t.Error("Expected READ-HOOK job, got none")
	}
}
