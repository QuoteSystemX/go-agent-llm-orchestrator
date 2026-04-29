package monitor

import (
	"context"
	"crypto/sha256"
	"fmt"
	"io"
	"log"
	"os"
	"path/filepath"
	"strings"
	"sync"

	"go-agent-llm-orchestrator/internal/db"
	"gopkg.in/yaml.v3"
)

type DriftStatus struct {
	RepoName  string   `json:"repo_name"`
	HasDrift  bool     `json:"has_drift"`
	DriftedFiles []string `json:"drifted_files"`
}

type DistributionConfig struct {
	Repositories []struct {
		Name string `json:"name"`
	} `json:"repositories"`
}

type DriftDetector struct {
	db          *db.DB
	hubPath     string
	repoBase    string
	lastResults []DriftStatus
	mu          sync.RWMutex
}

func NewDriftDetector(database *db.DB, hubPath, repoBase string) *DriftDetector {
	return &DriftDetector{
		db:       database,
		hubPath:  hubPath,
		repoBase: repoBase,
	}
}

func (d *DriftDetector) GetLastResults() []DriftStatus {
	d.mu.RLock()
	defer d.mu.RUnlock()
	return d.lastResults
}

func (d *DriftDetector) CheckDrift(ctx context.Context) ([]DriftStatus, error) {
	// 1. Read distribution.yml from Hub
	distPath := filepath.Join(d.hubPath, ".github", "distribution.yml")
	data, err := os.ReadFile(distPath)
	if err != nil {
		return nil, fmt.Errorf("reading distribution.yml: %w", err)
	}

	var config DistributionConfig
	if err := yaml.Unmarshal(data, &config); err != nil {
		return nil, fmt.Errorf("parsing distribution.yml: %w", err)
	}

	results := make([]DriftStatus, 0, len(config.Repositories))

	for _, repo := range config.Repositories {
		status := DriftStatus{RepoName: repo.Name}
		targetPath := filepath.Join(d.repoBase, repo.Name)

		// 2. Compare .agent and .claude folders
		driftFiles, err := d.compareDirectories(filepath.Join(d.hubPath, ".agent"), filepath.Join(targetPath, ".agent"))
		if err != nil {
			log.Printf("drift: warning: failed to compare .agent for %s: %v", repo.Name, err)
		}
		status.DriftedFiles = append(status.DriftedFiles, driftFiles...)

		driftFiles, err = d.compareDirectories(filepath.Join(d.hubPath, ".claude"), filepath.Join(targetPath, ".claude"))
		if err != nil {
			log.Printf("drift: warning: failed to compare .claude for %s: %v", repo.Name, err)
		}
		status.DriftedFiles = append(status.DriftedFiles, driftFiles...)

		if len(status.DriftedFiles) > 0 {
			status.HasDrift = true
		}
		results = append(results, status)
	}

	d.mu.Lock()
	d.lastResults = results
	d.mu.Unlock()

	return results, nil
}

func (d *DriftDetector) compareDirectories(hubDir, targetDir string) ([]string, error) {
	var drifted []string

	// Walk through hub directory
	err := filepath.Walk(hubDir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		if info.IsDir() {
			return nil
		}

		// Calculate relative path
		relPath, err := filepath.Rel(hubDir, path)
		if err != nil {
			return err
		}

		// Ignore certain files
		if d.shouldIgnore(relPath) {
			return nil
		}

		targetFilePath := filepath.Join(targetDir, relPath)
		
		// Check if file exists in target
		if _, err := os.Stat(targetFilePath); os.IsNotExist(err) {
			drifted = append(drifted, relPath+" (missing)")
			return nil
		}

		// Compare checksums
		hubHash, err := d.calculateHash(path)
		if err != nil {
			return err
		}
		targetHash, err := d.calculateHash(targetFilePath)
		if err != nil {
			return err
		}

		if hubHash != targetHash {
			drifted = append(drifted, relPath+" (diverged)")
		}

		return nil
	})

	return drifted, err
}

func (d *DriftDetector) shouldIgnore(path string) bool {
	ignored := []string{".DS_Store", "skill.lock", ".git"}
	for _, ign := range ignored {
		if strings.Contains(path, ign) {
			return true
		}
	}
	return false
}

func (d *DriftDetector) calculateHash(path string) (string, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer f.Close()

	h := sha256.New()
	if _, err := io.Copy(h, f); err != nil {
		return "", err
	}

	return fmt.Sprintf("%x", h.Sum(nil)), nil
}
