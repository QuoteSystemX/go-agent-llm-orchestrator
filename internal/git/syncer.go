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

// StartBackgroundReposSync periodically syncs all repositories found in the tasks table.
func (s *Syncer) StartBackgroundReposSync(ctx context.Context) {
	interval := s.getRefreshInterval()
	log.Printf("git: background repos syncer starting (interval: %v)", interval)
	
	ticker := time.Now() // Trigger immediately
	for {
		if time.Since(ticker) >= interval {
			ticker = time.Now()
			
			basePath := s.db.GetSetting("repo_base_path", "./data/repos")
			repos, err := s.db.GetDistinctRepos(ctx)
			if err != nil {
				log.Printf("git: failed to get distinct repos for sync: %v", err)
			} else {
				for _, repoName := range repos {
					repoPath := filepath.Join(basePath, repoName)
					rawUrl := fmt.Sprintf("https://github.com/%s.git", repoName)
					
					log.Printf("git: background sync for %s...", repoName)
					if err := s.SyncCustom(ctx, rawUrl, "main", repoPath); err != nil {
						log.Printf("git: sync failed for %s: %v", repoName, err)
					}
				}
			}
		}

		select {
		case <-ctx.Done():
			return
		case <-time.After(1 * time.Minute):
			// Check again in 1 minute
		}
	}
}

// Sync performs a clone (if repo not present) or pull (if already cloned) for the prompt library.
func (s *Syncer) Sync(ctx context.Context) error {
	rawUrl := s.db.GetSetting("prompt_library_git_url", "")
	if rawUrl == "" {
		log.Printf("git: NOT CONFIGURED — set git URL in Settings → Prompt Library")
		return fmt.Errorf("prompt_library_git_url not configured")
	}
	branch := s.db.GetSetting("prompt_library_git_branch", "main")

	return s.SyncCustom(ctx, rawUrl, branch, s.cacheDir)
}

// SyncCustom allows syncing any repository to a specific directory.
func (s *Syncer) SyncCustom(ctx context.Context, rawUrl, branch, targetDir string) error {
	pat := s.db.GetSetting("prompt_library_pat", "")
	if pat == "" {
		return fmt.Errorf("GitHub PAT not configured — set it via web UI Settings → Prompt Library")
	}

	// Ensure we use HTTPS and inject PAT
	syncUrl := s.prepareSyncURL(rawUrl, pat)

	if err := os.MkdirAll(filepath.Dir(targetDir), 0755); err != nil {
		return fmt.Errorf("creating cache parent dir: %w", err)
	}

	if _, err := os.Stat(filepath.Join(targetDir, ".git")); os.IsNotExist(err) {
		log.Printf("git: initializing %s (branch: %s) in %s", rawUrl, branch, targetDir)
		if err := os.MkdirAll(targetDir, 0755); err != nil {
			return fmt.Errorf("creating cache dir: %w", err)
		}
		if err := s.runGit(ctx, targetDir, "init"); err != nil {
			return err
		}
		
		// Set remote origin
		if err := s.runGit(ctx, targetDir, "remote", "add", "origin", syncUrl); err != nil {
			if strings.Contains(err.Error(), "already exists") {
				if err := s.runGit(ctx, targetDir, "remote", "set-url", "origin", syncUrl); err != nil {
					return fmt.Errorf("failed to reset remote origin: %w", err)
				}
			} else {
				return fmt.Errorf("failed to add remote origin: %w", err)
			}
		}
	} else {
		// Update remote URL in case PAT or URL changed
		if err := s.runGit(ctx, targetDir, "remote", "set-url", "origin", syncUrl); err != nil {
			return fmt.Errorf("failed to update remote origin: %w", err)
		}
	}

	log.Printf("git: syncing %s (branch: %s) to %s", rawUrl, branch, targetDir)
	if err := s.runGit(ctx, targetDir, "fetch", "--depth", "1", "origin", branch); err != nil {
		return fmt.Errorf("fetch failed: %w", err)
	}
	if err := s.runGit(ctx, targetDir, "reset", "--hard", "origin/"+branch); err != nil {
		return fmt.Errorf("reset failed: %w", err)
	}
	
	if targetDir == s.cacheDir {
		s.notifySyncSuccess()
	}
	return nil
}

// prepareSyncURL ensures the URL is HTTPS and includes the PAT for authentication.
func (s *Syncer) prepareSyncURL(rawUrl, pat string) string {
	finalUrl := rawUrl
	if strings.HasPrefix(rawUrl, "git@github.com:") {
		repoPath := strings.TrimPrefix(rawUrl, "git@github.com:")
		finalUrl = "https://github.com/" + repoPath
	}

	if pat == "" {
		return finalUrl
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
		safeArgs := strings.Join(args, " ")
		if pat != "" {
			errMsg = strings.ReplaceAll(errMsg, pat, "***")
			safeArgs = strings.ReplaceAll(safeArgs, pat, "***")
		}
		return fmt.Errorf("git %s: %w\n%s", safeArgs, err, errMsg)
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
