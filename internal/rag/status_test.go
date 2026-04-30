package rag

import (
	"context"
	"os"
	"testing"
)

func TestStoreInitialStatus(t *testing.T) {
	tempDir, err := os.MkdirTemp("", "rag-status-test-*")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(tempDir)

	repoID := "test/repo"
	
	// 1. New store should have 'initial' status if empty
	store := NewMemoryStore(tempDir, repoID, "http://localhost:11434", "nomic-embed-text")
	stats := store.GetStats()
	if stats.Status != "initial" {
		t.Errorf("Expected status 'initial' for empty store, got %s", stats.Status)
	}

	// 2. After indexing one file, it should transition to 'ok'
	store.MarkIndexed("file1.md", 12345)

	stats = store.GetStats()
	if stats.Status != "ok" {
		t.Errorf("Expected status 'ok' after indexing, got %s", stats.Status)
	}

	// 3. After recovery, it should go back to 'initial'
	err = store.Recover(context.Background())
	if err != nil {
		t.Fatalf("Recover failed: %v", err)
	}

	stats = store.GetStats()
	if stats.Status != "initial" {
		t.Errorf("Expected status 'initial' after recovery, got %s", stats.Status)
	}
	if stats.FilesIndexed != 0 {
		t.Errorf("Expected 0 files after recovery, got %d", stats.FilesIndexed)
	}
}

func TestSanitizeID(t *testing.T) {
	cases := []struct {
		input    string
		expected string
	}{
		{"org/repo", "org_repo"},
		{"org/sub/repo", "org_sub_repo"},
		{"../../etc/passwd", "____etc_passwd"},
		{"my-repo", "my-repo"},
	}

	for _, tc := range cases {
		got := SanitizeID(tc.input)
		if got != tc.expected {
			t.Errorf("SanitizeID(%s) = %s; want %s", tc.input, got, tc.expected)
		}
	}
}
