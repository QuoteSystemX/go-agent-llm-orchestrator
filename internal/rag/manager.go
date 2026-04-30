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
	stores := make(map[string]*MemoryStore)
	for k, v := range m.stores {
		stores[k] = v
	}
	m.mu.RUnlock()

	totalRemoved := 0
	for repoID, store := range stores {
		removed, err := store.Scrub(ctx)
		if err != nil {
			return totalRemoved, fmt.Errorf("scrub failed for %s: %w", repoID, err)
		}
		totalRemoved += removed
	}
	return totalRemoved, nil
}

// VerifyAll checks the health of all managed repositories.
func (m *Manager) VerifyAll(ctx context.Context) map[string]error {
	m.mu.RLock()
	stores := make(map[string]*MemoryStore)
	for k, v := range m.stores {
		stores[k] = v
	}
	m.mu.RUnlock()

	results := make(map[string]error)
	for repoID, store := range stores {
		if err := store.Verify(ctx); err != nil {
			results[repoID] = err
		}
	}
	return results
}

// RecoverRepo triggers recovery for a specific repository.
func (m *Manager) RecoverRepo(ctx context.Context, repoID string) error {
	m.mu.RLock()
	store, ok := m.stores[repoID]
	m.mu.RUnlock()

	if !ok {
		return fmt.Errorf("store not found for %s", repoID)
	}

	return store.Recover(ctx)
}
