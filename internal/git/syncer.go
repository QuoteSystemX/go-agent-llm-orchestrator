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

// Syncer clones and periodically pulls a git repo using a GitHub PAT (HTTPS).
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
	if s.OnSyncSuccess != nil {
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
	rawUrl := s.db.GetSetting("prompt_library_git_url", "")
	if rawUrl == "" {
		log.Printf("git: NOT CONFIGURED — set git URL in Settings → Prompt Library")
		return fmt.Errorf("prompt_library_git_url not configured")
	}
	branch := s.db.GetSetting("prompt_library_git_branch", "main")

	pat := s.db.GetSetting("prompt_library_pat", "")
	if pat == "" {
		log.Printf("git: NOT CONFIGURED — set GitHub PAT in Settings → Prompt Library")
		return fmt.Errorf("GitHub PAT not configured — set it via web UI Settings → Prompt Library")
	}

	// Ensure we use HTTPS and inject PAT
	syncUrl := s.prepareSyncURL(rawUrl, pat)

	if err := os.MkdirAll(filepath.Dir(s.cacheDir), 0755); err != nil {
		return fmt.Errorf("creating cache parent dir: %w", err)
	}

	if _, err := os.Stat(filepath.Join(s.cacheDir, ".git")); os.IsNotExist(err) {
		log.Printf("git: initializing %s (branch: %s) in %s", rawUrl, branch, s.cacheDir)
		if err := os.MkdirAll(s.cacheDir, 0755); err != nil {
			return fmt.Errorf("creating cache dir: %w", err)
		}
		if err := s.runGit(ctx, s.cacheDir, "init"); err != nil {
			return err
		}
		
		// Set remote origin
		if err := s.runGit(ctx, s.cacheDir, "remote", "add", "origin", syncUrl); err != nil {
			if strings.Contains(err.Error(), "already exists") {
				if err := s.runGit(ctx, s.cacheDir, "remote", "set-url", "origin", syncUrl); err != nil {
					return fmt.Errorf("failed to reset remote origin: %w", err)
				}
			} else {
				return fmt.Errorf("failed to add remote origin: %w", err)
			}
		}
	} else {
		// Update remote URL in case PAT or URL changed
		if err := s.runGit(ctx, s.cacheDir, "remote", "set-url", "origin", syncUrl); err != nil {
			return fmt.Errorf("failed to update remote origin: %w", err)
		}
	}

	log.Printf("git: pulling %s (branch: %s)", rawUrl, branch)
	if err := s.runGit(ctx, s.cacheDir, "fetch", "--depth", "1", "origin", branch); err != nil {
		log.Printf("git: fetch FAILED: %v", err)
		return err
	}
	if err := s.runGit(ctx, s.cacheDir, "reset", "--hard", "origin/"+branch); err != nil {
		log.Printf("git: reset FAILED: %v", err)
		return err
	}
	log.Printf("git: pull OK")
	s.notifySyncSuccess()
	return nil
}

// prepareSyncURL ensures the URL is HTTPS and includes the PAT for authentication.
func (s *Syncer) prepareSyncURL(rawUrl, pat string) string {
	finalUrl := rawUrl
	if strings.HasPrefix(rawUrl, "git@github.com:") {
		repoPath := strings.TrimPrefix(rawUrl, "git@github.com:")
		finalUrl = "https://github.com/" + repoPath
	}

	if strings.HasPrefix(finalUrl, "https://") {
		pureUrl := strings.TrimPrefix(finalUrl, "https://")
		if idx := strings.Index(pureUrl, "@"); idx != -1 {
			pureUrl = pureUrl[idx+1:]
		}
		return fmt.Sprintf("https://%s@%s", pat, pureUrl)
	}
	return finalUrl
}

// SyncNow triggers an immediate sync and blocks until it completes.
func (s *Syncer) SyncNow(ctx context.Context) error {
	return s.Sync(ctx)
}

func (s *Syncer) runGit(ctx context.Context, dir string, args ...string) error {
	cmd := exec.CommandContext(ctx, "git", args...)
	cmd.Dir = dir
	
	// Use a dedicated .home directory inside the PVC to avoid cluttering the root data folder.
	homeDir := filepath.Join(filepath.Dir(s.cacheDir), ".home")
	if err := os.MkdirAll(homeDir, 0755); err != nil {
		return fmt.Errorf("failed to create git home directory: %w", err)
	}

	cmd.Env = append(os.Environ(),
		"HOME="+homeDir,
		"GIT_TERMINAL_PROMPT=0",
	)

	out, err := cmd.CombinedOutput()
	if err != nil {
		errMsg := string(out)
		pat := s.db.GetSetting("prompt_library_pat", "")
		if pat != "" {
			errMsg = strings.ReplaceAll(errMsg, pat, "***")
		}
		return fmt.Errorf("git %s: %w\n%s", strings.Join(args, " "), err, errMsg)
	}
	return nil
}

func (s *Syncer) getRefreshInterval() time.Duration {
	raw := s.db.GetSetting("prompt_library_refresh_interval", "1h")
	d, err := time.ParseDuration(raw)
	if err != nil {
		return time.Hour
	}
	return d
}

func (s *Syncer) IsPATConfigured() bool {
	return s.db.GetSetting("prompt_library_pat", "") != ""
}
