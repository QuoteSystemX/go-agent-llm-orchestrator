package main

import (
	"database/sql"
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
	go idx.FullScan()

	go idx.Watch()

	go func() {
		ticker := time.NewTicker(1 * time.Hour)
		for range ticker.C {
			idx.FullScan()
		}
	}()
}

func (idx *Indexer) FullScan() {
	fmt.Fprintf(os.Stderr, "Indexer: Starting full project scan...\n")

	tx, err := idx.db.conn.Begin()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Indexer: Failed to start transaction: %v\n", err)
		return
	}
	defer tx.Rollback()

	for _, d := range idx.indexDirs {
		path := filepath.Join(idx.projectRoot, d)
		if _, err := os.Stat(path); err != nil {
			continue
		}
		filepath.Walk(path, func(p string, info os.FileInfo, err error) error {
			if err != nil || info.IsDir() {
				return nil
			}
			if strings.HasSuffix(p, ".md") || strings.HasSuffix(p, ".log") {
				idx.IndexFileTx(tx, p)
			}
			return nil
		})
	}

	if err := tx.Commit(); err != nil {
		fmt.Fprintf(os.Stderr, "Indexer: Failed to commit full scan: %v\n", err)
	} else {
		fmt.Fprintf(os.Stderr, "Indexer: Full scan completed successfully.\n")
	}
}

func (idx *Indexer) IndexFileTx(tx *sql.Tx, path string) {
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

	_, err = tx.Exec(
		`INSERT INTO documents (path, content, type)
		 VALUES ($1, $2, $3)
		 ON CONFLICT (path) DO UPDATE SET content=EXCLUDED.content, type=EXCLUDED.type`,
		rel, string(content), docType,
	)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Indexer error indexing %s: %v\n", rel, err)
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

	_, err = idx.db.conn.Exec(
		`INSERT INTO documents (path, content, type)
		 VALUES ($1, $2, $3)
		 ON CONFLICT (path) DO UPDATE SET content=EXCLUDED.content, type=EXCLUDED.type`,
		rel, string(content), docType,
	)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Indexer error indexing %s: %v\n", rel, err)
	}
}

func (idx *Indexer) TriggerHooks(relPath, eventType string, fullPath string, prefix string) {
	hooks, _ := idx.db.GetHooksForResource(relPath, eventType)
	for _, h := range hooks {
		fmt.Fprintf(os.Stderr, "Hook Trigger: %s on %s [%s]\n", h.ScriptPath, relPath, eventType)
		jobID := fmt.Sprintf("%s-%d", prefix, time.Now().UnixNano()) // nosec
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
	for _, d := range idx.indexDirs {
		path := filepath.Join(idx.projectRoot, d)
		if _, err := os.Stat(path); err == nil {
			idx.watcher.Add(path)
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
			if event.Op&(fsnotify.Write|fsnotify.Create) != 0 {
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
	rows, err := idx.db.conn.Query(`
		SELECT path, type,
		       ts_headline('english', content, plainto_tsquery('english', $1),
		                   'MaxWords=64,MinWords=20,StartSel=<b>,StopSel=</b>,HighlightAll=false') AS snippet
		FROM documents
		WHERE to_tsvector('english', coalesce(content,'')) @@ plainto_tsquery('english', $1)
		ORDER BY ts_rank(to_tsvector('english', coalesce(content,'')), plainto_tsquery('english', $1)) DESC
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
