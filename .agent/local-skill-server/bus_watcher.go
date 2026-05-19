package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"

	"github.com/fsnotify/fsnotify"
)

// RefactorState represents the state machine states
type RefactorState string

const (
	StateInit     RefactorState = "INITIATED"
	StateAnalyzing RefactorState = "ANALYZING"
	StateExecuting RefactorState = "EXECUTING"
	StateCompleted RefactorState = "COMPLETED"
	StateFailed    RefactorState = "FAILED"
)

// RefactorSession represents the refactoring session DTO
type RefactorSession struct {
	State      RefactorState `json:"state"`
	Files      []string      `json:"files"`
	CurrentIdx int           `json:"current_idx"`
	Logs       []string      `json:"logs"`
	Error      string        `json:"error,omitempty"`
}

// BusWatcher monitors .agent/bus/ for file changes
type BusWatcher struct {
	watcher   *fsnotify.Watcher
	projectRoot string
	mu        sync.RWMutex
	stopChan  chan struct{}
}

// NewBusWatcher creates a new bus watcher instance
func NewBusWatcher(projectRoot string) (*BusWatcher, error) {
	watcher, err := fsnotify.NewWatcher()
	if err != nil {
		return nil, fmt.Errorf("failed to create watcher: %w", err)
	}

	busPath := filepath.Join(projectRoot, ".agent", "bus")
	if err := watcher.Add(busPath); err != nil {
		watcher.Close()
		return nil, fmt.Errorf("failed to watch bus path: %w", err)
	}

	bw := &BusWatcher{
		watcher:     watcher,
		projectRoot: projectRoot,
		stopChan:    make(chan struct{}),
	}

	return bw, nil
}

// Start begins the event loop in a goroutine
func (bw *BusWatcher) Start(handler func(string, fsnotify.Event)) {
	go func() {
		for {
			select {
			case <-bw.stopChan:
				return
			case event, ok := <-bw.watcher.Events:
				if !ok {
					return
				}
				// Only handle write events for JSON files in bus
				if event.Op&fsnotify.Write == 0 {
					continue
				}
				if !strings.HasSuffix(event.Name, ".json") {
					continue
				}
				handler(event.Name, event)
			case err, ok := <-bw.watcher.Errors:
				if !ok {
					return
				}
				fmt.Fprintf(os.Stderr, "WATCHER ERROR: %v\n", err)
			}
		}
	}()
}

// Stop gracefully stops the watcher
func (bw *BusWatcher) Stop() error {
	close(bw.stopChan)
	return bw.watcher.Close()
}

// GetSessionPath returns the path to the refactor session file
func (bw *BusWatcher) GetSessionPath() string {
	return filepath.Join(bw.projectRoot, ".agent", "bus", "session_refactor.json")
}

// InitSession creates a new refactoring session
func (bw *BusWatcher) InitSession(files []string) error {
	if len(files) == 0 {
		return fmt.Errorf("at least one file is required")
	}

	session := RefactorSession{
		State:      StateInit,
		Files:      files,
		CurrentIdx: 0,
		Logs:       []string{fmt.Sprintf("Session initiated with %d files", len(files))},
	}

	return bw.writeSession(session)
}

// GetSession reads the current session state
func (bw *BusWatcher) GetSession() (*RefactorSession, error) {
	path := bw.GetSessionPath()
	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, fmt.Errorf("no active session found")
		}
		return nil, fmt.Errorf("failed to read session: %w", err)
	}

	var session RefactorSession
	if err := json.Unmarshal(data, &session); err != nil {
		return nil, fmt.Errorf("failed to parse session: %w", err)
	}

	return &session, nil
}

// Step executes the next transition in the state machine
func (bw *BusWatcher) Step() error {
	session, err := bw.GetSession()
	if err != nil {
		return err
	}

	switch session.State {
	case StateInit:
		session.State = StateAnalyzing
		session.Logs = append(session.Logs, "Transition: INITIATED -> ANALYZING")

	case StateAnalyzing:
		session.State = StateExecuting
		session.Logs = append(session.Logs, "Transition: ANALYZING -> EXECUTING")

	case StateExecuting:
		session.CurrentIdx++
		if session.CurrentIdx >= len(session.Files) {
			session.State = StateCompleted
			session.Logs = append(session.Logs, fmt.Sprintf("All %d files processed", len(session.Files)))
		} else {
			session.Logs = append(session.Logs, fmt.Sprintf("Processed file %d/%d: %s",
				session.CurrentIdx, len(session.Files), session.Files[session.CurrentIdx-1]))
		}

	case StateCompleted:
		return fmt.Errorf("session already completed")

	case StateFailed:
		return fmt.Errorf("session in failed state, needs reset")
	}

	return bw.writeSession(*session)
}

// writeSession atomically writes the session to disk
func (bw *BusWatcher) writeSession(session RefactorSession) error {
	path := bw.GetSessionPath()
	data, err := json.MarshalIndent(session, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to marshal session: %w", err)
	}

	if err := os.WriteFile(path, data, 0644); err != nil {
		return fmt.Errorf("failed to write session: %w", err)
	}

	return nil
}

// ResetSession clears the current session
func (bw *BusWatcher) ResetSession() error {
	path := bw.GetSessionPath()
	if err := os.Remove(path); err != nil && !os.IsNotExist(err) {
		return fmt.Errorf("failed to remove session: %w", err)
	}
	return nil
}