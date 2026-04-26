package rag

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/philippgille/chromem-go"
)

// Document represents a piece of text (chunk) indexed for search.
// Category classifies the origin: "meta" for wiki/tasks/README/.agent files
// (high-value for BMAD stage detection) and "code" for all other source files.
type Document struct {
	ID       string
	Content  string
	Source   string
	Category string
}

// RAGStats provides insights into the vector database state.
type RAGStats struct {
	RepoID          string    `json:"repo_id"`
	FilesIndexed    int       `json:"files_indexed"`
	ChunkCount      int       `json:"chunk_count"`
	LastScrubbedAt  time.Time `json:"last_scrubbed_at"`
	IndexPath       string    `json:"index_path"`
	OllamaEndpoint  string    `json:"ollama_endpoint"`
	EmbeddingModel  string    `json:"embedding_model"`
}

// MemoryStore is an in-memory/persistent storage for RAG using chromem-go
type MemoryStore struct {
	mu         sync.RWMutex
	db         *chromem.DB
	collection *chromem.Collection
	indexed    map[string]int64
	indexPath  string
	repoID     string
	ollamaUrl  string
	modelName  string
	// inferMu is the shared Ollama priority gate owned by llm.Router.
	inferMu *sync.RWMutex
}

// newOllamaEmbedFunc returns an EmbeddingFunc that calls the Ollama /api/embeddings
// endpoint with num_ctx capped at 2048 to match nomic-embed-text's training context.
// chromem-go's built-in NewEmbeddingFuncOllama does not expose this option, which
// causes Ollama to default to 8192 and emit a WARN on every model load.
func newOllamaEmbedFunc(modelName, baseURL string) chromem.EmbeddingFunc {
	client := &http.Client{Timeout: 60 * time.Second}
	return func(ctx context.Context, text string) ([]float32, error) {
		payload := map[string]interface{}{
			"model":  modelName,
			"prompt": text,
			"options": map[string]interface{}{
				"num_ctx": 2048,
			},
		}
		body, err := json.Marshal(payload)
		if err != nil {
			return nil, fmt.Errorf("embed marshal: %w", err)
		}

		req, err := http.NewRequestWithContext(ctx, http.MethodPost, baseURL+"/embeddings", bytes.NewReader(body))
		if err != nil {
			return nil, fmt.Errorf("embed request: %w", err)
		}
		req.Header.Set("Content-Type", "application/json")

		resp, err := client.Do(req)
		if err != nil {
			return nil, fmt.Errorf("embed call: %w", err)
		}
		defer resp.Body.Close()

		if resp.StatusCode != http.StatusOK {
			b, _ := io.ReadAll(resp.Body)
			return nil, fmt.Errorf("embed status %d: %s", resp.StatusCode, b)
		}

		var result struct {
			Embedding []float32 `json:"embedding"`
		}
		if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
			return nil, fmt.Errorf("embed decode: %w", err)
		}
		return result.Embedding, nil
	}
}

// NewMemoryStore initializes a persistent chromem DB for a specific repository
func NewMemoryStore(basePath string, repoID string, ollamaUrl string, modelName string) *MemoryStore {
	// sanitize repoID for filesystem
	safeRepoID := strings.ReplaceAll(repoID, "/", "_")
	dbPath := filepath.Join(basePath, safeRepoID)
	os.MkdirAll(dbPath, 0755)

	db, err := chromem.NewPersistentDB(dbPath, false)
	if err != nil {
		log.Printf("RAG Error: Failed to init chromem DB for %s: %v. Falling back to in-memory.", repoID, err)
		db = chromem.NewDB()
	}

	if ollamaUrl != "" && !strings.HasSuffix(ollamaUrl, "/api") {
		for strings.HasSuffix(ollamaUrl, "/") {
			ollamaUrl = strings.TrimSuffix(ollamaUrl, "/")
		}
		ollamaUrl = ollamaUrl + "/api"
	}
	embedFunc := newOllamaEmbedFunc(modelName, ollamaUrl)

	collection, err := db.GetOrCreateCollection("repo_context", nil, embedFunc)
	if err != nil {
		log.Printf("RAG Error: Failed to create collection for %s: %v", repoID, err)
	}

	indexPath := filepath.Join(dbPath, "rag_index.json")
	indexed := make(map[string]int64)
	if data, err := os.ReadFile(indexPath); err == nil {
		if err := json.Unmarshal(data, &indexed); err != nil {
			log.Printf("RAG Warning: Failed to parse %s. Resetting index cache.", indexPath)
			indexed = make(map[string]int64)
			os.Remove(indexPath)
		}
	}

	if collection != nil && len(indexed) > 0 && collection.Count() == 0 {
		log.Printf("RAG Warning: Vector DB for %s is empty but index cache exists. Forcing full reindex.", repoID)
		indexed = make(map[string]int64)
		os.Remove(indexPath)
	}

	return &MemoryStore{
		db:         db,
		collection: collection,
		indexed:    indexed,
		indexPath:  indexPath,
		repoID:     repoID,
		ollamaUrl:  ollamaUrl,
		modelName:  modelName,
	}
}

// RepoID returns the repository identifier for this store
func (s *MemoryStore) RepoID() string {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.repoID
}

// SetInferencePriority wires up the Ollama priority gate from llm.Router.
func (s *MemoryStore) SetInferencePriority(mu *sync.RWMutex) {
	s.inferMu = mu
}

// AddDocument adds and indexes a new document using embeddings
func (s *MemoryStore) AddDocument(ctx context.Context, doc Document) error {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.collection == nil {
		return fmt.Errorf("collection is nil")
	}

	// Hold a read-lock on the inference gate while the Ollama embedding call is
	// in-flight. A concurrent inference request (write-lock) waits for this
	// chunk to finish before taking the Ollama slot.
	if s.inferMu != nil {
		s.inferMu.RLock()
		defer s.inferMu.RUnlock()
	}

	err := s.collection.AddDocuments(ctx, []chromem.Document{
		{
			ID:      doc.ID,
			Content: doc.Content,
			Metadata: map[string]string{
				"source":   doc.Source,
				"category": doc.Category,
			},
		},
	}, 1) // 1 thread for local
	if err != nil {
		if strings.Contains(err.Error(), "connection refused") {
			log.Printf("RAG Critical Error: Ollama is not accessible. Ensure it's running and 'nomic-embed-text' model is pulled. Error: %v", err)
		} else {
			log.Printf("RAG Error: failed to add doc %s: %v", doc.ID, err)
		}
		return err
	}
	return nil
}

// Search performs semantic search across all documents.
func (s *MemoryStore) Search(ctx context.Context, query string, topK int) []Document {
	return s.SearchFiltered(ctx, query, topK, "")
}

// SearchFiltered performs semantic search restricted to a specific category.
// Pass an empty category to search all documents (equivalent to Search).
func (s *MemoryStore) SearchFiltered(ctx context.Context, query string, topK int, category string) []Document {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.collection == nil {
		return nil
	}

	var where map[string]string
	if category != "" {
		where = map[string]string{"category": category}
	}

	results, err := s.collection.Query(ctx, query, topK, where, nil)
	if err != nil {
		log.Printf("RAG Error: query failed (category=%q): %v", category, err)
		return nil
	}

	var docs []Document
	for _, res := range results {
		docs = append(docs, Document{
			ID:       res.ID,
			Content:  res.Content,
			Source:   res.Metadata["source"],
			Category: res.Metadata["category"],
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

// RemoveDocumentsBySource deletes all chunks for a given source file from the vector DB.
func (s *MemoryStore) RemoveDocumentsBySource(ctx context.Context, source string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.collection == nil {
		return nil
	}
	err := s.collection.Delete(ctx, map[string]string{"source": source}, nil)
	if err == nil {
		delete(s.indexed, source)
	}
	return err
}

// Scrub checks all indexed files and removes those that no longer exist on disk.
func (s *MemoryStore) Scrub(ctx context.Context) (int, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	if s.collection == nil {
		return 0, fmt.Errorf("collection not initialized")
	}

	removed := 0
	var missingSources []string

	// 1. Identify missing files
	for source := range s.indexed {
		if _, err := os.Stat(source); os.IsNotExist(err) {
			missingSources = append(missingSources, source)
		}
	}

	// 2. Remove from vector DB and local cache
	for _, source := range missingSources {
		log.Printf("RAG Scrub [%s]: Removing deleted file from index: %s", s.repoID, source)
		err := s.collection.Delete(ctx, map[string]string{"source": source}, nil)
		if err != nil {
			log.Printf("RAG Scrub [%s] Error: failed to delete %s: %v", s.repoID, source, err)
			continue
		}
		delete(s.indexed, source)
		removed++
	}

	if removed > 0 {
		s.SaveIndex()
	}

	return removed, nil
}

// GetStats returns current metrics for this repository's vector store.
func (s *MemoryStore) GetStats() RAGStats {
	s.mu.RLock()
	defer s.mu.RUnlock()

	var lastScrubbed time.Time
	if info, err := os.Stat(s.indexPath); err == nil {
		lastScrubbed = info.ModTime()
	}

	chunkCount := 0
	if s.collection != nil {
		chunkCount = s.collection.Count()
	}

	return RAGStats{
		RepoID:         s.repoID,
		FilesIndexed:   len(s.indexed),
		ChunkCount:     chunkCount,
		LastScrubbedAt: lastScrubbed,
		IndexPath:      s.indexPath,
		OllamaEndpoint: s.ollamaUrl,
		EmbeddingModel: s.modelName,
	}
}

// IsIndexed checks if a source file is already indexed and up-to-date
func (s *MemoryStore) IsIndexed(source string, modTime int64) bool {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.indexed[source] >= modTime
}

// IndexedCount returns the number of files in the persistent index cache.
func (s *MemoryStore) IndexedCount() int {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return len(s.indexed)
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
