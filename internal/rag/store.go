package rag

import (
	"context"
	"log"
	"sync"

	"github.com/philippgille/chromem-go"
)

// Document represents a piece of text (chunk) indexed for search
type Document struct {
	ID      string
	Content string
	Source  string
}

// MemoryStore is an in-memory/persistent storage for RAG using chromem-go
type MemoryStore struct {
	mu         sync.RWMutex
	db         *chromem.DB
	collection *chromem.Collection
	indexed    map[string]bool
}

// NewMemoryStore initializes a persistent chromem DB for RAG
func NewMemoryStore(dbPath string, ollamaUrl string, modelName string) *MemoryStore {
	db, err := chromem.NewPersistentDB(dbPath, false)
	if err != nil {
		log.Printf("RAG Error: Failed to init chromem DB: %v. Falling back to in-memory.", err)
		db = chromem.NewDB()
	}

	embedFunc := chromem.NewEmbeddingFuncOllama(modelName, ollamaUrl)

	// Create or get collection
	collection, err := db.GetOrCreateCollection("repo_context", nil, embedFunc)
	if err != nil {
		log.Printf("RAG Error: Failed to create collection: %v", err)
	}

	return &MemoryStore{
		db:         db,
		collection: collection,
		indexed:    make(map[string]bool),
	}
}

// AddDocument adds and indexes a new document using embeddings
func (s *MemoryStore) AddDocument(ctx context.Context, doc Document) {
	s.mu.Lock()
	defer s.mu.Unlock()

	if s.collection == nil {
		return
	}

	err := s.collection.AddDocuments(ctx, []chromem.Document{
		{
			ID:      doc.ID,
			Content: doc.Content,
			Metadata: map[string]string{
				"source": doc.Source,
			},
		},
	}, 1) // 1 thread for local
	if err != nil {
		log.Printf("RAG Error: failed to add doc %s: %v", doc.ID, err)
	}
}

// Search performs semantic search
func (s *MemoryStore) Search(ctx context.Context, query string, topK int) []Document {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.collection == nil {
		return nil
	}

	results, err := s.collection.Query(ctx, query, topK, nil, nil)
	if err != nil {
		log.Printf("RAG Error: query failed: %v", err)
		return nil
	}

	var docs []Document
	for _, res := range results {
		source := ""
		if src, ok := res.Metadata["source"]; ok {
			source = src
		}
		docs = append(docs, Document{
			ID:      res.ID,
			Content: res.Content,
			Source:  source,
		})
	}

	return docs
}

// Reset clears all documents
func (s *MemoryStore) Reset(ctx context.Context) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.indexed = make(map[string]bool)
	if s.db != nil {
		s.db.DeleteCollection("repo_context")
		// EmbedFunc would need to be passed again, so usually we don't hard reset
		// in this basic implementation, we just clear the indexed map and rely on AddDocument overwriting.
	}
}

// IsIndexed checks if a source file is already indexed
func (s *MemoryStore) IsIndexed(source string) bool {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.indexed[source]
}

// MarkIndexed marks a source file as indexed
func (s *MemoryStore) MarkIndexed(source string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.indexed[source] = true
}
