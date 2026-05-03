package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"time"
)

func (h *handler) retentionLoop() {
	ticker := time.NewTicker(24 * time.Hour)
	defer ticker.Stop()

	for range ticker.C {
		retentionDaysStr := h.db.GetSetting("retention_days", "30")
		days, err := strconv.Atoi(retentionDaysStr)
		if err != nil {
			days = 30
		}

		fmt.Fprintf(os.Stderr, "Running retention cleanup (older than %d days)...\n", days)
		if err := h.db.CleanupOldData(days); err != nil {
			fmt.Fprintf(os.Stderr, "Retention cleanup failed: %v\n", err)
		}
	}
}

func resolveProjectRoot() string {
	cwd, _ := os.Getwd()
	// Walk up until we find .agent
	curr := cwd
	for {
		if _, err := os.Stat(filepath.Join(curr, ".agent")); err == nil {
			return curr
		}
		parent := filepath.Dir(curr)
		if parent == curr {
			break
		}
		curr = parent
	}
	// Fallback to go.mod
	curr = cwd
	for {
		if _, err := os.Stat(filepath.Join(curr, "go.mod")); err == nil {
			return curr
		}
		parent := filepath.Dir(curr)
		if parent == curr {
			break
		}
		curr = parent
	}
	return cwd
}
