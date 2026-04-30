package rag

import (
	"os"
	"testing"
)

func TestIndexingStatus(t *testing.T) {
	tmpDir, _ := os.MkdirTemp("", "rag-test-*")
	defer os.RemoveAll(tmpDir)

	store := NewMemoryStore(tmpDir, "test-repo", "", "test-model")
	
	// 1. Initial state
	stats := store.GetStats()
	if stats.Status != "initial" {
		t.Errorf("Expected status 'initial', got %s", stats.Status)
	}

	// 2. Set total files but indexed is still 0
	store.SetTotalFiles(10)
	stats = store.GetStats()
	if stats.Status != "initial" {
		t.Errorf("Expected status 'initial' even with totalFiles set, got %s", stats.Status)
	}

	// 3. Index some files (partial)
	store.MarkIndexed("file1.go", 123)
	stats = store.GetStats()
	if stats.Status != "indexing" {
		t.Errorf("Expected status 'indexing', got %s", stats.Status)
	}
	if stats.FilesIndexed != 1 || stats.TotalFiles != 10 {
		t.Errorf("Stats mismatch: %d/%d", stats.FilesIndexed, stats.TotalFiles)
	}

	// 4. Index all files
	for i := 2; i <= 10; i++ {
		store.MarkIndexed("file.go", int64(i)) // Overwriting same ID or adding new ones
	}
	// Chromem-go might count unique IDs, but our store.indexed map counts paths.
	// Let's use unique paths for the test.
	for i := 2; i <= 10; i++ {
		store.MarkIndexed(string(rune(i)), int64(i))
	}

	stats = store.GetStats()
	if stats.Status != "ok" {
		t.Errorf("Expected status 'ok', got %s", stats.Status)
	}
}
