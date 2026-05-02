package backup

import (
	"bytes"
	"context"
	"os"
	"path/filepath"
	"testing"

	"go-agent-llm-orchestrator/internal/db"
)

func TestBackupRestore(t *testing.T) {
	// 1. Setup temp data directory
	tmpDir, err := os.MkdirTemp("", "backup-test-*")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(tmpDir)

	dbPath := filepath.Join(tmpDir, "tasks.db")
	database, err := db.InitDB(dbPath)
	if err != nil {
		t.Fatal(err)
	}

	// Add some dummy data to DB
	_, err = database.Exec("INSERT INTO settings (key, value) VALUES ('test_key', 'test_value')")
	if err != nil {
		t.Fatal(err)
	}

	// Add some dummy files
	reposDir := filepath.Join(tmpDir, "repos")
	if err := os.MkdirAll(reposDir, 0755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(reposDir, "test.txt"), []byte("hello world"), 0644); err != nil {
		t.Fatal(err)
	}

	mgr := NewManager(database, tmpDir)
	password := "secret123"

	// 2. Export
	var buf bytes.Buffer
	err = mgr.Export(context.Background(), password, &buf)
	if err != nil {
		t.Fatalf("Export failed: %v", err)
	}

	if buf.Len() == 0 {
		t.Fatal("Exported buffer is empty")
	}

	// 3. Modify data before import
	_, err = database.Exec("UPDATE settings SET value = 'new_value' WHERE key = 'test_key'")
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(reposDir, "test.txt"), []byte("modified"), 0644); err != nil {
		t.Fatal(err)
	}

	// 4. Import
	applyFunc, err := mgr.Import(context.Background(), password, bytes.NewReader(buf.Bytes()), int64(buf.Len()))
	if err != nil {
		t.Fatalf("Import failed: %v", err)
	}

	// Close DB to ensure files can be replaced
	database.Close()

	if err := applyFunc(); err != nil {
		t.Fatalf("Apply failed: %v", err)
	}

	// 5. Verify data is restored
	database, err = db.InitDB(dbPath)
	if err != nil {
		t.Fatal(err)
	}
	defer database.Close()

	var val string
	err = database.QueryRow("SELECT value FROM settings WHERE key = 'test_key'").Scan(&val)
	if err != nil {
		t.Fatal(err)
	}
	if val != "test_value" {
		t.Errorf("Expected 'test_value', got '%s'", val)
	}

	content, err := os.ReadFile(filepath.Join(reposDir, "test.txt"))
	if err != nil {
		t.Fatal(err)
	}
	if string(content) != "hello world" {
		t.Errorf("Expected 'hello world', got '%s'", string(content))
	}
}

func TestImportInvalidPassword(t *testing.T) {
	tmpDir, _ := os.MkdirTemp("", "backup-test-*")
	defer os.RemoveAll(tmpDir)

	dbPath := filepath.Join(tmpDir, "tasks.db")
	database, _ := db.InitDB(dbPath)
	mgr := NewManager(database, tmpDir)

	var buf bytes.Buffer
	mgr.Export(context.Background(), "correct-password", &buf)

	_, err := mgr.Import(context.Background(), "wrong-password", bytes.NewReader(buf.Bytes()), int64(buf.Len()))
	if err == nil {
		t.Error("Import should have failed with wrong password")
	}
}
