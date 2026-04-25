package rag

import (
	"strings"
	"sync"
)

// Document represents a piece of text (chunk) indexed for search
type Document struct {
	ID      string
	Content string
	Source  string
}

// MemoryStore is a simple in-memory storage for RAG
type MemoryStore struct {
	mu    sync.RWMutex
	docs  []Document
}

func NewMemoryStore() *MemoryStore {
	return &MemoryStore{
		docs: []Document{},
	}
}

// AddDocument adds and indexes a new document
func (s *MemoryStore) AddDocument(doc Document) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.docs = append(s.docs, doc)
}

// Search performs a simple keyword-based search with stop-word filtering and improved scoring
func (s *MemoryStore) Search(query string, topK int) []Document {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if len(s.docs) == 0 {
		return nil
	}

	stopWords := map[string]bool{
		"the": true, "and": true, "for": true, "with": true, "this": true,
		"that": true, "from": true, "your": true, "have": true, "will": true,
		"package": true, "import": true, "func": true, "type": true, "struct": true,
	}

	type scoredDoc struct {
		doc   Document
		score float64
	}

	queryTerms := strings.Fields(strings.ToLower(query))
	filteredTerms := []string{}
	for _, term := range queryTerms {
		if len(term) > 2 && !stopWords[term] {
			filteredTerms = append(filteredTerms, term)
		}
	}

	if len(filteredTerms) == 0 {
		filteredTerms = queryTerms // fallback if all were filtered
	}

	var scored []scoredDoc

	for _, doc := range s.docs {
		score := 0.0
		contentLower := strings.ToLower(doc.Content)
		
		uniqueMatches := 0
		for _, term := range filteredTerms {
			count := strings.Count(contentLower, term)
			if count > 0 {
				// Score = log(count+1) to dampen high frequency + bonus for unique term match
				score += 1.0 + float64(count)*0.1
				uniqueMatches++
			}
		}

		if score > 0 {
			// Boost documents that match more unique terms from the query
			score *= float64(uniqueMatches)
			scored = append(scored, scoredDoc{doc, score})
		}
	}

	// Sort by score (descending)
	for i := 0; i < len(scored); i++ {
		for j := i + 1; j < len(scored); j++ {
			if scored[j].score > scored[i].score {
				scored[i], scored[j] = scored[j], scored[i]
			}
		}
	}

	resultLimit := topK
	if len(scored) < topK {
		resultLimit = len(scored)
	}

	results := make([]Document, resultLimit)
	for i := 0; i < resultLimit; i++ {
		results[i] = scored[i].doc
	}

	return results
}

// Reset clears all documents
func (s *MemoryStore) Reset() {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.docs = []Document{}
}
