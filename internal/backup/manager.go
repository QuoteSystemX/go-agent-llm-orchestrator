package backup

import (
	"context"
	"fmt"
	"io"
	"os"
	"path/filepath"

	"go-agent-llm-orchestrator/internal/db"
	passwordzip "github.com/alexmullins/zip"
)

type Manager struct {
	db      *db.DB
	dataDir string
}

func NewManager(database *db.DB, dataDir string) *Manager {
	return &Manager{
		db:      database,
		dataDir: dataDir,
	}
}

func (m *Manager) DataDir() string {
	return m.dataDir
}

// Export creates a password-protected ZIP archive containing databases and data directories.
func (m *Manager) Export(ctx context.Context, password string, w io.Writer) error {
	// 1. Create temp directory for DB snapshots in the data directory (which is writable)
	tempDir, err := os.MkdirTemp(m.dataDir, "backup-tmp-*")
	if err != nil {
		return err
	}
	defer os.RemoveAll(tempDir)

	tasksSnapshot := filepath.Join(tempDir, "tasks.db")
	historySnapshot := filepath.Join(tempDir, "history.db")

	// 2. Take DB snapshots
	if err := m.db.BackupMain(ctx, tasksSnapshot); err != nil {
		return fmt.Errorf("backup main db: %w", err)
	}
	if err := m.db.BackupHistory(ctx, historySnapshot); err != nil {
		return fmt.Errorf("backup history db: %w", err)
	}

	// 3. Create ZIP archive
	zw := passwordzip.NewWriter(w)
	defer zw.Close()

	// Helper to add file to zip
	addFile := func(path, name string) error {
		f, err := os.Open(path)
		if err != nil {
			return err
		}
		defer f.Close()

		var header io.Writer
		var zipErr error
		if password != "" {
			header, zipErr = zw.Encrypt(name, password)
		} else {
			header, zipErr = zw.Create(name)
		}
		if zipErr != nil {
			return zipErr
		}

		_, err = io.Copy(header, f)
		return err
	}

	// Helper to add directory to zip
	addDir := func(dirPath, zipBase string) error {
		return filepath.Walk(dirPath, func(path string, info os.FileInfo, err error) error {
			if err != nil {
				return err
			}
			if info.IsDir() {
				return nil
			}
			rel, err := filepath.Rel(dirPath, path)
			if err != nil {
				return err
			}
			zipPath := filepath.Join(zipBase, rel)
			return addFile(path, zipPath)
		})
	}

	// Add DBs
	if err := addFile(tasksSnapshot, "tasks.db"); err != nil {
		return err
	}
	if err := addFile(historySnapshot, "history.db"); err != nil {
		return err
	}

	// Add repos and prompt-lib
	reposDir := filepath.Join(m.dataDir, "repos")
	if _, err := os.Stat(reposDir); err == nil {
		if err := addDir(reposDir, "repos"); err != nil {
			return err
		}
	}

	promptLibDir := filepath.Join(m.dataDir, "prompt-lib")
	if _, err := os.Stat(promptLibDir); err == nil {
		if err := addDir(promptLibDir, "prompt-lib"); err != nil {
			return err
		}
	}

	return nil
}

// Import extracts a password-protected ZIP archive and returns a function to apply it.
// The apply function should be called when it's safe to overwrite files (engines stopped).
func (m *Manager) Import(ctx context.Context, password string, r io.ReaderAt, size int64) (func() error, error) {
	zr, err := passwordzip.NewReader(r, size)
	if err != nil {
		return nil, err
	}

	// 1. Verify password by trying to open the first file
	if len(zr.File) > 0 {
		f := zr.File[0]
		if password != "" {
			f.SetPassword(password)
		}
		rc, err := f.Open()
		if err != nil {
			return nil, fmt.Errorf("invalid password or corrupted archive: %w", err)
		}
		rc.Close()
	}

	// 2. Extract to a temporary directory in dataDir
	tempExtractDir, err := os.MkdirTemp(m.dataDir, "import-tmp-*")
	if err != nil {
		return nil, err
	}

	for _, f := range zr.File {
		if password != "" {
			f.SetPassword(password)
		}
		rc, err := f.Open()
		if err != nil {
			os.RemoveAll(tempExtractDir)
			return nil, err
		}

		path := filepath.Join(tempExtractDir, f.Name)
		if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
			rc.Close()
			os.RemoveAll(tempExtractDir)
			return nil, err
		}

		dst, err := os.Create(path)
		if err != nil {
			rc.Close()
			os.RemoveAll(tempExtractDir)
			return nil, err
		}

		_, err = io.Copy(dst, rc)
		dst.Close()
		rc.Close()
		if err != nil {
			os.RemoveAll(tempExtractDir)
			return nil, err
		}
	}

	// Return a closure that will apply the changes
	applyFunc := func() error {
		defer os.RemoveAll(tempExtractDir)

		// Replace DBs
		dbFiles := []string{"tasks.db", "history.db"}
		for _, dbFile := range dbFiles {
			src := filepath.Join(tempExtractDir, dbFile)
			dst := filepath.Join(m.dataDir, dbFile)
			if _, err := os.Stat(src); err == nil {
				if err := copyFile(src, dst); err != nil {
					return err
				}
			}
		}

		// Replace directories
		dirs := []string{"repos", "prompt-lib"}
		for _, dir := range dirs {
			src := filepath.Join(tempExtractDir, dir)
			dst := filepath.Join(m.dataDir, dir)
			if _, err := os.Stat(src); err == nil {
				os.RemoveAll(dst)
				if err := copyDir(src, dst); err != nil {
					return err
				}
			}
		}
		return nil
	}

	return applyFunc, nil
}

func copyFile(src, dst string) error {
	s, err := os.Open(src)
	if err != nil {
		return err
	}
	defer s.Close()
	d, err := os.Create(dst)
	if err != nil {
		return err
	}
	defer d.Close()
	_, err = io.Copy(d, s)
	return err
}

func copyDir(src, dst string) error {
	return filepath.Walk(src, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		rel, err := filepath.Rel(src, path)
		if err != nil {
			return err
		}
		target := filepath.Join(dst, rel)
		if info.IsDir() {
			return os.MkdirAll(target, 0755)
		}
		return copyFile(path, target)
	})
}
