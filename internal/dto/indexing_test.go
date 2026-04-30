package dto

import (
	"context"
	"io/ioutil"
	"os"
	"path/filepath"
	"testing"
	"time"

	"go-agent-llm-orchestrator/internal/rag"
)

func TestIndexingProgressAccuracy(t *testing.T) {
	tmpDir, _ := ioutil.TempDir("", "dto-test-*")
	defer os.RemoveAll(tmpDir)

	repoDir := filepath.Join(tmpDir, "repo")
	os.MkdirAll(repoDir, 0755)

	// Create 3 files
	files := []string{"a.go", "b.go", "c.go"}
	for _, f := range files {
		ioutil.WriteFile(filepath.Join(repoDir, f), []byte("package main"), 0644)
	}

	// We don't need a full Analyzer to test the RAG counting logic
	// but we can test the rag.MemoryStore directly
	store := rag.NewMemoryStore(tmpDir, "test/repo", "", "")

	// 1. Manually "index" 3 files (including one that doesn't exist on disk yet)
	modTime := time.Now().Unix()
	store.MarkIndexed(filepath.Join(repoDir, "a.go"), modTime)
	store.MarkIndexed(filepath.Join(repoDir, "b.go"), modTime)
	store.MarkIndexed(filepath.Join(repoDir, "stale.go"), modTime)
	
	// 2. Delete one file from disk (simulate stale index)
	os.Remove(filepath.Join(repoDir, "a.go"))
	
	// Now: 
	// - Disk has "b.go", "c.go" (Total 2)
	// - Index has "a.go" (stale), "b.go" (active), "stale.go" (stale) (Total 3)
	
	if store.IndexedCount() != 3 {
		t.Errorf("Expected 3 indexed files, got %d", store.IndexedCount())
	}

	// 3. Run a "Scrub" (This is what we should call before starting analysis)
	removed, _ := store.Scrub(context.Background(), nil)
	if removed != 2 { // a.go and stale.go
		t.Errorf("Expected 2 files to be scrubbed, got %d", removed)
	}

	if store.IndexedCount() != 1 { // Only b.go remains
		t.Errorf("Expected 1 indexed file after scrub, got %d", store.IndexedCount())
	}

	// 3b. Test Filter-based scrubbing (The new feature)
	// Currently b.go is indexed and exists on disk.
	// Let's index c.go too.
	store.MarkIndexed(filepath.Join(repoDir, "c.go"), modTime)
	if store.IndexedCount() != 2 {
		t.Errorf("Expected 2 indexed files, got %d", store.IndexedCount())
	}
	
	// Run scrub with a filter that only allows .py files (so b.go and c.go should be removed)
	filter := func(path string) bool {
		return filepath.Ext(path) == ".py"
	}
	removed, _ = store.Scrub(context.Background(), filter)
	if removed != 2 {
		t.Errorf("Expected 2 files to be removed by filter, got %d", removed)
	}
	if store.IndexedCount() != 0 {
		t.Errorf("Expected 0 indexed files after filter scrub, got %d", store.IndexedCount())
	}
	
	// 4. Verify total count calculation logic used in Analyzer
	totalAllFiles := 0
	targetExts := map[string]bool{".go": true}
	filepath.Walk(repoDir, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() { return nil }
		if targetExts[filepath.Ext(path)] {
			totalAllFiles++
		}
		return nil
	})
	
	if totalAllFiles != 2 {
		t.Errorf("Expected 2 files on disk, got %d", totalAllFiles)
	}
}
