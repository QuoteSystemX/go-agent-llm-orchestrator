package rag

import (
	"context"
	"testing"
)

func TestMemoryStore_Basic(t *testing.T) {
	// For CI or environments without Ollama, we just test the initialization
	// and fallback mechanisms.
	s := NewMemoryStore("", "http://invalid-url:9999", "test-model")
	if s == nil {
		t.Fatal("expected MemoryStore, got nil")
	}

	ctx := context.Background()
	// Adding document will likely fail inside chromem due to invalid embed URL,
	// but the application should not panic.
	s.AddDocument(ctx, Document{ID: "1", Content: "test content", Source: "test.txt"})

	results := s.Search(ctx, "test query", 10)
	if len(results) > 0 {
		t.Logf("Got %d results, expected 0 due to invalid URL", len(results))
	}

	s.Reset(ctx)

	s.MarkIndexed("test.txt", 100)
	if !s.IsIndexed("test.txt", 100) {
		t.Error("expected test.txt to be indexed with modTime 100")
	}
}
