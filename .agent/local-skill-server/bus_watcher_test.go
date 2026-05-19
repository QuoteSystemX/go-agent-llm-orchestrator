package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestRefactorSessionStateMachine(t *testing.T) {
	// Create a temp project root
	tempDir := t.TempDir()
	busDir := filepath.Join(tempDir, ".agent", "bus")
	if err := os.MkdirAll(busDir, 0755); err != nil {
		t.Fatalf("failed to create bus dir: %v", err)
	}

	// Create watcher
	bw, err := NewBusWatcher(tempDir)
	if err != nil {
		t.Fatalf("failed to create watcher: %v", err)
	}
	defer bw.Stop()

	t.Run("InitSession creates valid session", func(t *testing.T) {
		files := []string{"file1.go", "file2.go", "file3.go"}
		if err := bw.InitSession(files); err != nil {
			t.Fatalf("InitSession failed: %v", err)
		}

		session, err := bw.GetSession()
		if err != nil {
			t.Fatalf("GetSession failed: %v", err)
		}

		if session.State != StateInit {
			t.Errorf("expected state INITIATED, got %s", session.State)
		}
		if len(session.Files) != 3 {
			t.Errorf("expected 3 files, got %d", len(session.Files))
		}
		if session.CurrentIdx != 0 {
			t.Errorf("expected idx 0, got %d", session.CurrentIdx)
		}
	})

	t.Run("Step transitions from INITIATED to ANALYZING", func(t *testing.T) {
		if err := bw.Step(); err != nil {
			t.Fatalf("Step failed: %v", err)
		}

		session, err := bw.GetSession()
		if err != nil {
			t.Fatalf("GetSession failed: %v", err)
		}

		if session.State != StateAnalyzing {
			t.Errorf("expected state ANALYZING, got %s", session.State)
		}
	})

	t.Run("Step transitions from ANALYZING to EXECUTING", func(t *testing.T) {
		if err := bw.Step(); err != nil {
			t.Fatalf("Step failed: %v", err)
		}

		session, err := bw.GetSession()
		if err != nil {
			t.Fatalf("GetSession failed: %v", err)
		}

		if session.State != StateExecuting {
			t.Errorf("expected state EXECUTING, got %s", session.State)
		}
	})

	t.Run("Step increments file index", func(t *testing.T) {
		if err := bw.Step(); err != nil {
			t.Fatalf("Step failed: %v", err)
		}

		session, err := bw.GetSession()
		if err != nil {
			t.Fatalf("GetSession failed: %v", err)
		}

		if session.CurrentIdx != 1 {
			t.Errorf("expected idx 1, got %d", session.CurrentIdx)
		}
	})

	t.Run("Step completes when all files processed", func(t *testing.T) {
		// Continue stepping until complete
		for i := 0; i < 3; i++ {
			if err := bw.Step(); err != nil {
				break
			}
		}

		session, err := bw.GetSession()
		if err != nil {
			t.Fatalf("GetSession failed: %v", err)
		}

		if session.State != StateCompleted {
			t.Errorf("expected state COMPLETED, got %s", session.State)
		}
	})

	t.Run("Step returns error when session completed", func(t *testing.T) {
		err := bw.Step()
		if err == nil {
			t.Error("expected error on completed session")
		}
	})

	t.Run("GetSession returns error when no session", func(t *testing.T) {
		// Reset - remove session file
		if err := bw.ResetSession(); err != nil {
			t.Fatalf("ResetSession failed: %v", err)
		}

		_, err := bw.GetSession()
		if err == nil {
			t.Error("expected error when no session")
		}
	})
}

func TestInitSessionRequiresFiles(t *testing.T) {
	tempDir := t.TempDir()
	busDir := filepath.Join(tempDir, ".agent", "bus")
	if err := os.MkdirAll(busDir, 0755); err != nil {
		t.Fatalf("failed to create bus dir: %v", err)
	}

	bw, err := NewBusWatcher(tempDir)
	if err != nil {
		t.Fatalf("failed to create watcher: %v", err)
	}
	defer bw.Stop()

	err = bw.InitSession([]string{})
	if err == nil {
		t.Error("expected error for empty files list")
	}
}

func TestGetSessionPath(t *testing.T) {
	tempDir := "/test/project"
	bw := &BusWatcher{projectRoot: tempDir}

	path := bw.GetSessionPath()
	expected := filepath.Join(tempDir, ".agent", "bus", "session_refactor.json")
	if path != expected {
		t.Errorf("expected %s, got %s", expected, path)
	}
}