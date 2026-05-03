package main

import (
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	"github.com/mark3labs/mcp-go/mcp"
)

func (h *handler) updateJob(id string, progress int, message string) {
	h.db.conn.Exec("UPDATE jobs SET progress = ?, message = ? WHERE id = ?", progress, message, id)
}

func (h *handler) finishJob(id string, status string) {
	h.db.conn.Exec("UPDATE jobs SET status = ?, progress = 100, completed_at = ? WHERE id = ?", status, time.Now(), id)
}

func validatePath(path string) error {
	if strings.Contains(path, "..") {
		return fmt.Errorf("invalid path traversal attempt")
	}
	if filepath.IsAbs(path) {
		return fmt.Errorf("absolute paths are not allowed")
	}
	return nil
}

func sanitizeString(s string) string {
	// Allow dots and slashes for paths, but strip suspicious sequences
	s = strings.ReplaceAll(s, "..", "")
	reg, _ := regexp.Compile("[^a-zA-Z0-9_/.-]+")
	return reg.ReplaceAllString(s, "")
}

func (h *handler) listItemsHelper(path string, isDir bool) (*mcp.CallToolResult, error) {
	entries, err := os.ReadDir(path)
	if err != nil {
		return mcp.NewToolResultError("failed to read directory: " + err.Error()), nil
	}
	var names []string
	for _, e := range entries {
		if strings.HasPrefix(e.Name(), ".") {
			continue
		}
		if isDir && e.IsDir() {
			names = append(names, e.Name())
		} else if !isDir && !e.IsDir() {
			names = append(names, e.Name())
		}
	}
	return mcp.NewToolResultText(strings.Join(names, "\n")), nil
}
