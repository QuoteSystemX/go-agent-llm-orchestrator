package main

import (
	"os"
	"path/filepath"
	"testing"
)

func setupTestDB(t *testing.T) (*DB, func()) {
	dbPath := filepath.Join(t.TempDir(), "test.db")
	db, err := InitDB(dbPath)
	if err != nil {
		t.Fatal(err)
	}
	return db, func() {
		db.conn.Close()
	}
}

func TestIndexer_IndexingAndSearch(t *testing.T) {
	db, cleanup := setupTestDB(t)
	defer cleanup()

	tempDir, err := os.MkdirTemp("", "indexer-test")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(tempDir)

	idx, err := NewIndexer(db, tempDir, []string{"docs"}, nil)
	if err != nil {
		t.Fatal(err)
	}

	// Create a test file
	docsDir := filepath.Join(tempDir, "docs")
	os.MkdirAll(docsDir, 0755)
	testFile := filepath.Join(docsDir, "test.md")
	content := "This is a secret document about security and encryption."
	if err := os.WriteFile(testFile, []byte(content), 0644); err != nil {
		t.Fatal(err)
	}

	// Index the file
	idx.IndexFile(testFile)

	// Search for "security"
	results, err := idx.Search("security")
	if err != nil {
		t.Fatalf("Search failed: %v", err)
	}

	if len(results) == 0 {
		t.Fatal("Expected at least one result, got 0")
	}

	if results[0]["path"] != "docs/test.md" {
		t.Errorf("Expected path docs/test.md, got %s", results[0]["path"])
	}

	if !testing.Short() {
		// Test porter stemming (security -> secur)
		results, _ = idx.Search("secured")
		if len(results) == 0 {
			t.Log("Warning: Porter stemming might not be active in this sqlite build")
		} else {
			t.Log("Porter stemming confirmed")
		}
	}
}

func TestIndexer_FullScan(t *testing.T) {
	db, cleanup := setupTestDB(t)
	defer cleanup()

	tempDir, err := os.MkdirTemp("", "indexer-scan-test")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(tempDir)

	// Setup structure
	dirs := []string{".agent", "wiki", "tasks"}
	for _, d := range dirs {
		dirPath := filepath.Join(tempDir, d)
		os.MkdirAll(dirPath, 0755)
		os.WriteFile(filepath.Join(dirPath, "info.md"), []byte("Information in "+d), 0644)
	}

	idx, _ := NewIndexer(db, tempDir, dirs, nil)
	idx.FullScan()

	// Verify all 3 files are indexed
	var count int
	err = db.conn.QueryRow("SELECT COUNT(*) FROM documents_fts").Scan(&count)
	if err != nil {
		t.Fatal(err)
	}

	if count != 3 {
		t.Errorf("Expected 3 indexed documents, got %d", count)
	}

	// Search for "Information"
	results, _ := idx.Search("Information")
	if len(results) != 3 {
		t.Errorf("Expected 3 matches for 'Information', got %d", len(results))
	}
}
