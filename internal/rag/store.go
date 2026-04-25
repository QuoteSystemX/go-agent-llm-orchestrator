package rag

import (
	"context"
	"encoding/json"
	"log"
	"os"
	"path/filepath"
	"strings"
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
	indexed    map[string]int64
	indexPath  string
}

// NewMemoryStore initializes a persistent chromem DB for RAG
func NewMemoryStore(dbPath string, ollamaUrl string, modelName string) *MemoryStore {
	db, err := chromem.NewPersistentDB(dbPath, false)
	if err != nil {
		log.Printf("RAG Error: Failed to init chromem DB: %v. Falling back to in-memory.", err)
		db = chromem.NewDB()
	}

	if ollamaUrl != "" && !strings.HasSuffix(ollamaUrl, "/api") {
		// Ensure it doesn't end with a slash before adding /api
		for strings.HasSuffix(ollamaUrl, "/") {
			ollamaUrl = strings.TrimSuffix(ollamaUrl, "/")
		}
		ollamaUrl = ollamaUrl + "/api"
	}
	embedFunc := chromem.NewEmbeddingFuncOllama(modelName, ollamaUrl)

	// Create or get collection
	collection, err := db.GetOrCreateCollection("repo_context", nil, embedFunc)
	if err != nil {
		log.Printf("RAG Error: Failed to create collection: %v", err)
	}

	indexPath := filepath.Join(dbPath, "rag_index.json")
	indexed := make(map[string]int64)
	if data, err := os.ReadFile(indexPath); err == nil {
		if err := json.Unmarshal(data, &indexed); err != nil {
			log.Printf("RAG Warning: Failed to parse %s (corrupted JSON). Resetting index cache.", indexPath)
			indexed = make(map[string]int64)
			os.Remove(indexPath)
		}
	}

	// Protection against out-of-sync states: if DB is empty but we think files are indexed
	if collection != nil && len(indexed) > 0 && collection.Count() == 0 {
		log.Printf("RAG Warning: Vector DB is empty but index cache exists. Forcing full reindex.")
		indexed = make(map[string]int64)
		os.Remove(indexPath)
	}

	return &MemoryStore{
		db:         db,
		collection: collection,
		indexed:    indexed,
		indexPath:  indexPath,
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
		if strings.Contains(err.Error(), "connection refused") {
			log.Printf("RAG Critical Error: Ollama is not accessible. Ensure it's running and 'nomic-embed-text' model is pulled. Error: %v", err)
		} else {
			log.Printf("RAG Error: failed to add doc %s: %v", doc.ID, err)
		}
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
	s.indexed = make(map[string]int64)
	if s.db != nil {
		s.db.DeleteCollection("repo_context")
	}
	os.Remove(s.indexPath)
}

// IsIndexed checks if a source file is already indexed and up-to-date
func (s *MemoryStore) IsIndexed(source string, modTime int64) bool {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.indexed[source] >= modTime
}

// MarkIndexed marks a source file as indexed with a specific modification time
func (s *MemoryStore) MarkIndexed(source string, modTime int64) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.indexed[source] = modTime
}

// SaveIndex saves the indexing state to disk safely
func (s *MemoryStore) SaveIndex() {
	s.mu.RLock()
	defer s.mu.RUnlock()
	data, err := json.Marshal(s.indexed)
	if err == nil {
		os.MkdirAll(filepath.Dir(s.indexPath), 0755)
		tmpPath := s.indexPath + ".tmp"
		if err := os.WriteFile(tmpPath, data, 0644); err == nil {
			os.Rename(tmpPath, s.indexPath) // Atomic replacement
		} else {
			log.Printf("RAG Error: Failed to write temp index file: %v", err)
		}
	}
}
