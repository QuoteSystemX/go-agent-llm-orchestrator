package api

import (
	"io"
	"log"
	"os"
	"strings"
	"sync"
	"time"
)

// LogEntry is a single captured log line.
type LogEntry struct {
	Time    string `json:"time"`
	Message string `json:"msg"`
}

// LogBuffer is a thread-safe circular buffer that captures log output.
type LogBuffer struct {
	mu      sync.RWMutex
	entries []LogEntry
	max     int
}

// NewLogBuffer creates a buffer of capacity max and redirects the default
// logger to write to both stderr and the buffer.
func NewLogBuffer(max int) *LogBuffer {
	b := &LogBuffer{max: max}
	log.SetOutput(io.MultiWriter(os.Stderr, b))
	return b
}

func (b *LogBuffer) Write(p []byte) (int, error) {
	msg := strings.TrimRight(string(p), "\n\r")
	if msg == "" {
		return len(p), nil
	}
	b.mu.Lock()
	b.entries = append(b.entries, LogEntry{
		Time:    time.Now().Format("15:04:05"),
		Message: msg,
	})
	if len(b.entries) > b.max {
		b.entries = b.entries[len(b.entries)-b.max:]
	}
	b.mu.Unlock()
	return len(p), nil
}

// Entries returns a copy of all buffered log entries (oldest first).
func (b *LogBuffer) Entries() []LogEntry {
	b.mu.RLock()
	defer b.mu.RUnlock()
	out := make([]LogEntry, len(b.entries))
	copy(out, b.entries)
	return out
}
