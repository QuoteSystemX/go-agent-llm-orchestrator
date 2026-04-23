package git

import (
	"context"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"go-agent-llm-orchestrator/internal/db"
)

// Syncer clones and periodically pulls a git repo using an SSH key.
// Priority for SSH key: YAML config (loaded into DB on startup) → DB setting (set via web UI).
type Syncer struct {
	db            *db.DB
	cacheDir      string // where to clone the repo locally
	OnSyncSuccess func() // called once after the first successful sync
	syncedOnce    bool
}

func NewSyncer(database *db.DB, cacheDir string) *Syncer {
	return &Syncer{db: database, cacheDir: cacheDir}
}

// CacheDir returns the local directory where the repo is cloned.
func (s *Syncer) CacheDir() string { return s.cacheDir }

func (s *Syncer) notifySyncSuccess() {
	if !s.syncedOnce && s.OnSyncSuccess != nil {
		s.syncedOnce = true
		s.OnSyncSuccess()
	}
}

// Start runs an initial sync and then re-syncs on the configured interval.
func (s *Syncer) Start(ctx context.Context) {
	interval := s.getRefreshInterval()
	log.Printf("git: syncer starting (interval: %v, cache: %s)", interval, s.cacheDir)

	if err := s.Sync(ctx); err != nil {
		log.Printf("git: initial sync FAILED: %v", err)
	} else {
		log.Printf("git: initial sync OK — prompt-library is ready")
	}

	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			log.Printf("git: syncer stopped")
			return
		case <-ticker.C:
			if err := s.Sync(ctx); err != nil {
				log.Printf("git: periodic sync FAILED: %v", err)
			} else {
				log.Printf("git: periodic sync OK")
			}
		}
	}
}

// Sync performs a clone (if repo not present) or pull (if already cloned).
func (s *Syncer) Sync(ctx context.Context) error {
	url := s.getSetting("prompt_library_git_url", "")
	if url == "" {
		log.Printf("git: NOT CONFIGURED — set git URL in Settings → Prompt Library")
		return fmt.Errorf("prompt_library_git_url not configured")
	}
	branch := s.getSetting("prompt_library_git_branch", "main")

	keyContent := s.getSetting("prompt_library_ssh_key", "")
	if keyContent == "" {
		log.Printf("git: NOT CONFIGURED — set SSH key in Settings → Prompt Library")
		return fmt.Errorf("SSH key not configured — set it via web UI Settings → Prompt Library")
	}

	// Write key to temp file
	keyFile, err := s.writeTempKey(keyContent)
	if err != nil {
		return fmt.Errorf("writing temp SSH key: %w", err)
	}
	defer os.Remove(keyFile)

	sshCmd := fmt.Sprintf("ssh -i %s -o StrictHostKeyChecking=accept-new -o BatchMode=yes", keyFile)

	if err := os.MkdirAll(filepath.Dir(s.cacheDir), 0755); err != nil {
		return fmt.Errorf("creating cache parent dir: %w", err)
	}

	if _, err := os.Stat(filepath.Join(s.cacheDir, ".git")); os.IsNotExist(err) {
		log.Printf("git: initializing %s (branch: %s) in %s", url, branch, s.cacheDir)
		if err := os.MkdirAll(s.cacheDir, 0755); err != nil {
			return fmt.Errorf("creating cache dir: %w", err)
		}
		if err := s.runGit(ctx, sshCmd, s.cacheDir, "init"); err != nil {
			return err
		}
		// Remote might already exist if init was partially successful
		_ = s.runGit(ctx, sshCmd, s.cacheDir, "remote", "remove", "origin")
		if err := s.runGit(ctx, sshCmd, s.cacheDir, "remote", "add", "origin", url); err != nil {
			return err
		}
	}

	log.Printf("git: pulling %s (branch: %s)", url, branch)
	if err := s.runGit(ctx, sshCmd, s.cacheDir, "fetch", "--depth", "1", "origin", branch); err != nil {
		return err
	}
	if err := s.runGit(ctx, sshCmd, s.cacheDir, "reset", "--hard", "origin/"+branch); err != nil {
		return err
	}
	log.Printf("git: pull OK")
	s.notifySyncSuccess()
	return nil
}

// SyncNow triggers an immediate sync and blocks until it completes.
// Safe to call from any goroutine.
func (s *Syncer) SyncNow(ctx context.Context) error {
	return s.Sync(ctx)
}

func (s *Syncer) runGit(ctx context.Context, sshCmd, dir string, args ...string) error {
	cmd := exec.CommandContext(ctx, "git", args...)
	cmd.Dir = dir
	cmd.Env = append(os.Environ(), "GIT_SSH_COMMAND="+sshCmd)
	out, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("git %s: %w\n%s", strings.Join(args, " "), err, string(out))
	}
	return nil
}

func (s *Syncer) getSetting(key, def string) string {
	var val string
	if err := s.db.QueryRow("SELECT value FROM settings WHERE key = ?", key).Scan(&val); err != nil || val == "" {
		return def
	}
	return val
}

func (s *Syncer) getRefreshInterval() time.Duration {
	raw := s.getSetting("prompt_library_refresh_interval", "1h")
	d, err := time.ParseDuration(raw)
	if err != nil {
		return time.Hour
	}
	return d
}

func (s *Syncer) IsSSHKeyConfigured() bool {
	return s.getSetting("prompt_library_ssh_key", "") != ""
}

func (s *Syncer) writeTempKey(content string) (string, error) {
	tmpDir := filepath.Join(filepath.Dir(s.cacheDir), ".ssh-tmp")
	if err := os.MkdirAll(tmpDir, 0755); err != nil {
		return "", fmt.Errorf("creating ssh-tmp dir: %w", err)
	}
	f, err := os.CreateTemp(tmpDir, "jules-ssh-key-*")
	if err != nil {
		return "", err
	}
	if err := os.Chmod(f.Name(), 0600); err != nil {
		f.Close()
		os.Remove(f.Name())
		return "", err
	}
	if _, err := f.WriteString(content); err != nil {
		f.Close()
		os.Remove(f.Name())
		return "", err
	}
	f.Close()
	return f.Name(), nil
}
