package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/fsnotify/fsnotify"
)

type Indexer struct {
	db          *DB
	projectRoot string
	indexDirs   []string
	dispatcher  *Dispatcher
	watcher     *fsnotify.Watcher
}

func NewIndexer(db *DB, projectRoot string, indexDirs []string, dispatcher *Dispatcher) (*Indexer, error) {
	watcher, err := fsnotify.NewWatcher()
	if err != nil {
		return nil, err
	}
	return &Indexer{
		db:          db,
		projectRoot: projectRoot,
		indexDirs:   indexDirs,
		dispatcher:  dispatcher,
		watcher:     watcher,
	}, nil
}

func (idx *Indexer) Start() {
	// 1. Initial Full Scan
	go idx.FullScan()

	// 2. Watch for changes
	go idx.Watch()

	// 3. Periodic Scan (once per hour)
	go func() {
		ticker := time.NewTicker(1 * time.Hour)
		for range ticker.C {
			idx.FullScan()
		}
	}()
}

func (idx *Indexer) FullScan() {
	fmt.Fprintf(os.Stderr, "Indexer: Starting full project scan...\n")
	dirs := idx.indexDirs
	for _, d := range dirs {
		path := filepath.Join(idx.projectRoot, d)
		if _, err := os.Stat(path); err != nil {
			continue
		}
		filepath.Walk(path, func(p string, info os.FileInfo, err error) error {
			if err != nil || info.IsDir() {
				return nil
			}
			if strings.HasSuffix(p, ".md") || strings.HasSuffix(p, ".log") {
				idx.IndexFile(p)
			}
			return nil
		})
	}
}

func (idx *Indexer) IndexFile(path string) {
	content, err := os.ReadFile(path)
	if err != nil {
		return
	}

	rel, _ := filepath.Rel(idx.projectRoot, path)
	docType := "doc"
	if strings.HasSuffix(path, ".log") {
		docType = "log"
	} else if strings.Contains(path, "tasks") {
		docType = "task"
	}

	// INSERT or REPLACE in FTS5 isn't direct like standard tables, 
	// we delete first then insert to ensure no duplicates.
	idx.db.conn.Exec("DELETE FROM documents_fts WHERE path = ?", rel)
	_, err = idx.db.conn.Exec("INSERT INTO documents_fts (path, content, type) VALUES (?, ?, ?)", 
		rel, string(content), docType)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Indexer error indexing %s: %v\n", rel, err)
	}
}

func (idx *Indexer) TriggerHooks(relPath, eventType string, fullPath string, prefix string) {
	hooks, _ := idx.db.GetHooksForResource(relPath, eventType)
	for _, h := range hooks {
		fmt.Fprintf(os.Stderr, "Hook Trigger: %s on %s [%s]\n", h.ScriptPath, relPath, eventType)
		jobID := fmt.Sprintf("%s-%d", prefix, time.Now().UnixNano())
		idx.db.SaveJob(&JobStatus{
			ID:        jobID,
			Name:      "Resource Hook: " + relPath,
			Status:    "pending",
			StartedAt: time.Now(),
		})
		idx.dispatcher.Submit(Task{
			JobID:   jobID,
			Command: h.ScriptPath,
			Args:    []string{fullPath},
		})
	}
}

func (idx *Indexer) Watch() {
	dirs := idx.indexDirs
	for _, d := range dirs {
		path := filepath.Join(idx.projectRoot, d)
		if _, err := os.Stat(path); err == nil {
			// fsnotify is not recursive by default, we need to add subdirs if needed.
			// For simplicity, we watch the main dirs.
			idx.watcher.Add(path)
			// Add subdirs
			filepath.Walk(path, func(p string, info os.FileInfo, err error) error {
				if err == nil && info.IsDir() {
					idx.watcher.Add(p)
				}
				return nil
			})
		}
	}

	for {
		select {
		case event, ok := <-idx.watcher.Events:
			if !ok {
				return
			}
			if event.Op&(fsnotify.Write|fsnotify.Create) !=0 {
				rel, _ := filepath.Rel(idx.projectRoot, event.Name)
				if strings.HasSuffix(event.Name, ".md") || strings.HasSuffix(event.Name, ".log") {
					idx.IndexFile(event.Name)
				}
				idx.TriggerHooks(rel, "on_change", event.Name, "HOOK")
			}
		case err, ok := <-idx.watcher.Errors:
			if !ok {
				return
			}
			fmt.Fprintf(os.Stderr, "Watcher error: %v\n", err)
		}
	}
}

func (idx *Indexer) Search(query string) ([]map[string]string, error) {
	// Using FTS5 highlight function for snippets
	rows, err := idx.db.conn.Query(`
		SELECT path, type, snippet(documents_fts, 1, '<b>', '</b>', '...', 64) as snippet
		FROM documents_fts 
		WHERE content MATCH ? 
		ORDER BY rank 
		LIMIT 20`, query)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var results []map[string]string
	for rows.Next() {
		var path, docType, snippet string
		if err := rows.Scan(&path, &docType, &snippet); err != nil {
			return nil, err
		}
		results = append(results, map[string]string{
			"path":    path,
			"type":    docType,
			"snippet": snippet,
		})
	}
	return results, nil
}
