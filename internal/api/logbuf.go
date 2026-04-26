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

// LogBuffer is a thread-safe circular buffer that captures log output
// and broadcasts it to active listeners (SSE).
type LogBuffer struct {
	mu        sync.RWMutex
	entries   []LogEntry
	max       int
	listeners map[chan LogEntry]bool
	hub       *Hub
}

// NewLogBuffer creates a buffer of capacity max and redirects the default
// logger to write to both stderr and the buffer.
func NewLogBuffer(max int) *LogBuffer {
	b := &LogBuffer{
		max:       max,
		listeners: make(map[chan LogEntry]bool),
	}
	log.SetOutput(io.MultiWriter(os.Stderr, b))
	return b
}

func (b *LogBuffer) Write(p []byte) (int, error) {
	msg := strings.TrimRight(string(p), "\n\r")
	if msg == "" {
		return len(p), nil
	}
	
	entry := LogEntry{
		Time:    time.Now().Format("15:04:05"),
		Message: msg,
	}

	b.mu.Lock()
	b.entries = append(b.entries, entry)
	if len(b.entries) > b.max {
		b.entries = b.entries[len(b.entries)-b.max:]
	}
	
	// Broadcast to WebSocket hub if available
	if b.hub != nil {
		b.hub.Broadcast(TypeLog, entry)
	}
	
	// Broadcast to all active SSE listeners (legacy)
	for ch := range b.listeners {
		select {
		case ch <- entry:
		default:
		}
	}
	b.mu.Unlock()

	return len(p), nil
}

// Subscribe returns a channel that will receive all new log entries.
func (b *LogBuffer) Subscribe() chan LogEntry {
	b.mu.Lock()
	defer b.mu.Unlock()
	ch := make(chan LogEntry, 10) // Buffer a few entries to avoid immediate drops
	b.listeners[ch] = true
	return ch
}

// Unsubscribe removes a listener channel.
func (b *LogBuffer) Unsubscribe(ch chan LogEntry) {
	b.mu.Lock()
	defer b.mu.Unlock()
	delete(b.listeners, ch)
	close(ch)
}

// Entries returns a copy of all buffered log entries (oldest first).
func (b *LogBuffer) Entries() []LogEntry {
	b.mu.RLock()
	defer b.mu.RUnlock()
	out := make([]LogEntry, len(b.entries))
	copy(out, b.entries)
	return out
}
// SetHub attaches a websocket hub for real-time broadcasting.
func (b *LogBuffer) SetHub(h *Hub) {
	b.mu.Lock()
	defer b.mu.Unlock()
	b.hub = h
}
