package db

import (
	"os"
	"testing"
)

func TestInitDB(t *testing.T) {
	dbPath := "./test_data/test.db"
	defer os.RemoveAll("./test_data")

	database, err := InitDB(dbPath)
	if err != nil {
		t.Fatalf("Failed to init DB: %v", err)
	}
	defer database.Close()

	// Check if tables exist
	var tableName string
	err = database.QueryRow("SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'").Scan(&tableName)
	if err != nil {
		t.Errorf("Table 'tasks' not found: %v", err)
	}

	if tableName != "tasks" {
		t.Errorf("Expected table 'tasks', got %s", tableName)
	}

	// Check WAL mode
	var journalMode string
	err = database.QueryRow("PRAGMA journal_mode").Scan(&journalMode)
	if err != nil {
		t.Errorf("Failed to check journal mode: %v", err)
	}
	if journalMode != "wal" {
		t.Errorf("Expected journal mode WAL, got %s", journalMode)
	}
}
