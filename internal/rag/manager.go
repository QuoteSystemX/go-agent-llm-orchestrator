package rag

import (
	"context"
	"fmt"
	"sync"
)

// Manager coordinates multiple MemoryStore instances.
type Manager struct {
	stores map[string]*MemoryStore
	mu     sync.RWMutex
}

// NewManager creates a new RAG Manager.
func NewManager() *Manager {
	return &Manager{
		stores: make(map[string]*MemoryStore),
	}
}

// RegisterStore adds a store to the manager.
func (m *Manager) RegisterStore(repoID string, store *MemoryStore) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.stores[repoID] = store
}

// GetStore retrieves a store by repoID.
func (m *Manager) GetStore(repoID string) *MemoryStore {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.stores[repoID]
}

// GetAllStats returns stats for all managed repositories.
func (m *Manager) GetAllStats() []RAGStats {
	m.mu.RLock()
	defer m.mu.RUnlock()

	var allStats []RAGStats
	for _, store := range m.stores {
		allStats = append(allStats, store.GetStats())
	}
	return allStats
}

// ScrubAll triggers scrubbing for all managed repositories.
func (m *Manager) ScrubAll(ctx context.Context) (int, error) {
	m.mu.RLock()
	defer m.mu.RUnlock()

	totalRemoved := 0
	for repoID, store := range m.stores {
		removed, err := store.Scrub(ctx)
		if err != nil {
			return totalRemoved, fmt.Errorf("scrub failed for %s: %w", repoID, err)
		}
		totalRemoved += removed
	}
	return totalRemoved, nil
}
