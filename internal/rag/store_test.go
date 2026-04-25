package rag

import (
	"testing"
)

func TestMemoryStore_Search_Basic(t *testing.T) {
	s := NewMemoryStore()
	s.AddDocument(Document{ID: "1", Content: "Go is a programming language", Source: "test1.txt"})
	s.AddDocument(Document{ID: "2", Content: "Python is another language", Source: "test2.txt"})

	results := s.Search("Go language", 10)
	if len(results) == 0 {
		t.Fatal("expected results, got none")
	}
	if results[0].ID != "1" {
		t.Errorf("expected doc 1 to be most relevant, got %s", results[0].ID)
	}
}

func TestMemoryStore_Search_StopWords(t *testing.T) {
	s := NewMemoryStore()
	// Doc A has many stop words
	s.AddDocument(Document{ID: "A", Content: "the package and the func are here", Source: "a.txt"})
	// Doc B has target keyword
	s.AddDocument(Document{ID: "B", Content: "specialized orchestration logic", Source: "b.txt"})

	// Searching for stop words + keyword
	results := s.Search("the package orchestration", 10)
	if len(results) == 0 {
		t.Fatal("expected results")
	}
	if results[0].ID != "B" {
		t.Errorf("expected doc B (with keyword) to be above doc A (with stop-words), got %s", results[0].ID)
	}
}

func TestMemoryStore_Search_UniqueMatches(t *testing.T) {
	s := NewMemoryStore()
	// Doc 1 has one keyword many times
	s.AddDocument(Document{ID: "1", Content: "apple apple apple apple apple", Source: "1.txt"})
	// Doc 2 has two keywords once
	s.AddDocument(Document{ID: "2", Content: "apple banana", Source: "2.txt"})

	// Searching for both
	results := s.Search("apple banana", 10)
	if len(results) < 2 {
		t.Fatal("expected 2 results")
	}
	// Doc 2 should win because it matches more unique terms
	if results[0].ID != "2" {
		t.Errorf("expected doc 2 to be most relevant due to unique matches, got %s", results[0].ID)
	}
}

func TestMemoryStore_Search_ShortWords(t *testing.T) {
	s := NewMemoryStore()
	s.AddDocument(Document{ID: "1", Content: "is it if it", Source: "1.txt"})
	s.AddDocument(Document{ID: "2", Content: "orchestrator", Source: "2.txt"})

	results := s.Search("is orchestrator", 10)
	if len(results) == 0 {
		t.Fatal("expected results")
	}
	if results[0].ID != "2" {
		t.Errorf("short words should be ignored, expected doc 2, got %s", results[0].ID)
	}
}

func TestMemoryStore_Reset(t *testing.T) {
	s := NewMemoryStore()
	s.AddDocument(Document{ID: "1", Content: "test", Source: "test.txt"})
	s.Reset()
	results := s.Search("test", 10)
	if len(results) != 0 {
		t.Errorf("expected 0 results after reset, got %d", len(results))
	}
}
