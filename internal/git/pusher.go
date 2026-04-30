package git

import (
	"context"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"go-agent-llm-orchestrator/internal/db"
)

type Pusher struct {
	db       *db.DB
	cacheDir string
}

func NewPusher(database *db.DB, cacheDir string) *Pusher {
	return &Pusher{db: database, cacheDir: cacheDir}
}

// CommitAndPush adds specific files, commits them with a message, and pushes to the remote branch.
func (p *Pusher) CommitAndPush(ctx context.Context, repoPath, branch string, files []string, message string) error {
	if err := p.ensureGitConfig(ctx, repoPath); err != nil {
		return fmt.Errorf("git config failed: %w", err)
	}

	// 1. Add files
	for _, file := range files {
		if err := p.runGit(ctx, repoPath, "add", file); err != nil {
			return fmt.Errorf("git add %s failed: %w", file, err)
		}
	}

	// 2. Check if there are changes to commit
	status, err := p.getGitOutput(ctx, repoPath, "status", "--porcelain")
	if err != nil {
		return fmt.Errorf("git status failed: %w", err)
	}
	if strings.TrimSpace(status) == "" {
		log.Printf("git: no changes to commit in %s", repoPath)
		return nil
	}

	// 3. Commit
	if err := p.runGit(ctx, repoPath, "commit", "-m", message); err != nil {
		return fmt.Errorf("git commit failed: %w", err)
	}

	// 4. Push
	// We use the same PAT logic as Syncer
	pat := p.db.GetSetting("prompt_library_pat", "")
	if pat == "" {
		return fmt.Errorf("GitHub PAT not configured")
	}

	// We need to ensure the remote URL has the PAT for pushing
	remoteURL, err := p.getGitOutput(ctx, repoPath, "remote", "get-url", "origin")
	if err != nil {
		return fmt.Errorf("failed to get remote URL: %w", err)
	}
	
	// Ensure PAT is in URL if it's HTTPS
	if strings.HasPrefix(remoteURL, "https://") && !strings.Contains(remoteURL, pat+"@") {
		// Re-prepare URL with PAT
		s := &Syncer{db: p.db}
		syncURL := s.prepareSyncURL(remoteURL, pat)
		if err := p.runGit(ctx, repoPath, "remote", "set-url", "origin", syncURL); err != nil {
			return fmt.Errorf("failed to update remote URL with PAT: %w", err)
		}
	}

	log.Printf("git: pushing changes to origin/%s in %s", branch, repoPath)
	if err := p.runGit(ctx, repoPath, "push", "origin", branch); err != nil {
		return fmt.Errorf("git push failed: %w", err)
	}

	return nil
}

func (p *Pusher) ensureGitConfig(ctx context.Context, repoPath string) error {
	userName := p.db.GetSetting("git_user_name", "Jules Orchestrator")
	userEmail := p.db.GetSetting("git_user_email", "jules@orchestrator.local")

	if err := p.runGit(ctx, repoPath, "config", "user.name", userName); err != nil {
		return err
	}
	return p.runGit(ctx, repoPath, "config", "user.email", userEmail)
}

func (p *Pusher) runGit(ctx context.Context, dir string, args ...string) error {
	_, err := p.getGitOutput(ctx, dir, args...)
	return err
}

func (p *Pusher) getGitOutput(ctx context.Context, dir string, args ...string) (string, error) {
	cmd := exec.CommandContext(ctx, "git", args...)
	cmd.Dir = dir
	
	homeDir := filepath.Join(filepath.Dir(p.cacheDir), ".home")
	cmd.Env = append(os.Environ(),
		"HOME="+homeDir,
		"GIT_TERMINAL_PROMPT=0",
	)

	out, err := cmd.CombinedOutput()
	if err != nil {
		errMsg := string(out)
		pat := p.db.GetSetting("prompt_library_pat", "")
		if pat != "" {
			errMsg = strings.ReplaceAll(errMsg, pat, "***")
		}
		return "", fmt.Errorf("git %s: %w\n%s", strings.Join(args, " "), err, errMsg)
	}
	return string(out), nil
}
