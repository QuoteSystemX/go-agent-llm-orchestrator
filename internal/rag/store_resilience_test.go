package rag

import (
	"context"
	"os"
	"path/filepath"
	"testing"
)

func TestMemoryStore_Resilience(t *testing.T) {
	tempDir, err := os.MkdirTemp("", "rag_resilience_test_*")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(tempDir)

	repoID := "test-repo"
	repoDir := filepath.Join(tempDir, repoID)
	err = os.MkdirAll(repoDir, 0755)
	if err != nil {
		t.Fatal(err)
	}

	// 1. Test normal initialization
	store := NewMemoryStore(tempDir, repoID, "", "dummy-model")
	if store == nil {
		t.Fatal("failed to create store")
	}
	stats := store.GetStats()
	if stats.Status != "ok" {
		t.Errorf("expected status ok, got %s", stats.Status)
	}
	if stats.StorageMode != "persistent" {
		t.Errorf("expected mode persistent, got %s", stats.StorageMode)
	}

	// 2. Test corruption detection (simulated)
	// We can't easily trigger a real chromem-go EOF error without deeper knowledge of its format,
	// but we can manually set the status and test Recovery.
	store.mu.Lock()
	store.status = "corrupted"
	store.mu.Unlock()

	if err := store.Verify(context.Background()); err == nil {
		t.Error("expected verify to fail for corrupted store")
	}

	// 3. Test Recovery
	err = store.Recover(context.Background())
	if err != nil {
		t.Errorf("recovery failed: %v", err)
	}

	stats = store.GetStats()
	if stats.Status != "ok" {
		t.Errorf("expected status ok after recovery, got %s", stats.Status)
	}
	if stats.StorageMode != "persistent" {
		t.Errorf("expected mode persistent after recovery, got %s", stats.StorageMode)
	}
}

func TestMemoryStore_EOF_Simulation(t *testing.T) {
	tempDir, err := os.MkdirTemp("", "rag_eof_test_*")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(tempDir)

	repoID := "eof-repo"
	repoDir := filepath.Join(tempDir, repoID)
	err = os.MkdirAll(repoDir, 0755)
	if err != nil {
		t.Fatal(err)
	}

	// Create a garbage file that might cause chromem-go to fail
	// chromem-go usually expects a 'collection.json' or similar if it's persistent.
	// Let's try to create a file that it might try to read.
	garbageFile := filepath.Join(repoDir, "collection.json")
	err = os.WriteFile(garbageFile, []byte("NOT A VALID JSON"), 0644)
	if err != nil {
		t.Fatal(err)
	}

	store := NewMemoryStore(tempDir, repoID, "", "dummy-model")
	stats := store.GetStats()
	
	// If chromem-go is robust it might just ignore garbage, 
	// but if it fails, our code should catch it.
	// This is a "best effort" test to see if we can trigger the corruption flag.
	t.Logf("Store Status: %s, Mode: %s", stats.Status, stats.StorageMode)
}
