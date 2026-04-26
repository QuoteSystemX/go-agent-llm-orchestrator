package rag

import (
	"context"
	"os"
	"testing"
)

func TestMemoryStore_Basic(t *testing.T) {
	tempDir, err := os.MkdirTemp("", "rag_test_*")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(tempDir)

	store := NewMemoryStore(tempDir, "test-repo", "", "dummy-model")
	if store == nil {
		t.Fatal("failed to create store")
	}

	store.MarkIndexed("test.txt", 100)
	if !store.IsIndexed("test.txt", 100) {
		t.Error("expected test.txt to be indexed")
	}

	if store.IndexedCount() != 1 {
		t.Errorf("expected 1 indexed file, got %d", store.IndexedCount())
	}

	stats := store.GetStats()
	if stats.RepoID != "test-repo" {
		t.Errorf("expected repo-id test-repo, got %s", stats.RepoID)
	}
}

func TestMemoryStore_Reset(t *testing.T) {
	tempDir, err := os.MkdirTemp("", "rag_reset_test_*")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(tempDir)

	store := NewMemoryStore(tempDir, "test-repo", "", "dummy-model")
	
	store.mu.Lock()
	store.indexed["some-file.txt"] = 123
	store.mu.Unlock()

	store.Reset(context.Background())

	stats := store.GetStats()
	if stats.FilesIndexed != 0 {
		t.Errorf("expected 0 indexed files after reset, got %d", stats.FilesIndexed)
	}
}
