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
	if envRoot := os.Getenv("PROJECT_ROOT"); envRoot != "" {
		return envRoot
	}
	if envWorkRoot := os.Getenv("WORKSPACE_ROOT"); envWorkRoot != "" {
		return envWorkRoot
	}

	cwd, _ := os.Getwd()
	// Walk up until we find a root marker
	curr := cwd
	for {
		// Check for .agent folder or GEMINI.md
		if _, err := os.Stat(filepath.Join(curr, ".agent")); err == nil {
			return curr
		}
		if _, err := os.Stat(filepath.Join(curr, "GEMINI.md")); err == nil {
			return curr
		}
		if _, err := os.Stat(filepath.Join(curr, "go.mod")); err == nil {
			return curr
		}

		parent := filepath.Dir(curr)
		if parent == curr {
			break
		}
		curr = parent
	}

	// Paperclip-specific discovery: if we are in /paperclip, look for workspaces
	if _, err := os.Stat("/paperclip/instances/default/workspaces"); err == nil {
		entries, _ := os.ReadDir("/paperclip/instances/default/workspaces")
		// Find the most recent directory that contains a .agent folder
		var bestMatch string
		var latestTime int64
		for _, e := range entries {
			if e.IsDir() {
				candidate := filepath.Join("/paperclip/instances/default/workspaces", e.Name())
				if info, err := os.Stat(filepath.Join(candidate, ".agent")); err == nil {
					if info.ModTime().Unix() > latestTime {
						latestTime = info.ModTime().Unix()
						bestMatch = candidate
					}
				}
			}
		}
		if bestMatch != "" {
			fmt.Fprintf(os.Stderr, "Paperclip discovery: selected workspace %s\n", bestMatch)
			return bestMatch
		}
	}

	return cwd
}
