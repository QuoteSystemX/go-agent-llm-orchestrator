package main

import (
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	"github.com/mark3labs/mcp-go/mcp"

	// Keep AWS SDK dependencies for S3 backups
	_ "github.com/aws/aws-sdk-go-v2/aws"
	_ "github.com/aws/aws-sdk-go-v2/config"
	_ "github.com/aws/aws-sdk-go-v2/service/s3"
)

func (h *handler) updateJob(id string, progress int, message string) {
	h.db.conn.Exec("UPDATE jobs SET progress = $1, message = $2 WHERE id = $3", progress, message, id)
}

func (h *handler) finishJob(id string, status string) {
	h.db.conn.Exec("UPDATE jobs SET status = $1, progress = 100, completed_at = $2 WHERE id = $3", status, time.Now(), id)
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

// slugify converts a human-readable label (e.g. "Adversarial Prompt Testing")
// into the kebab-case form used for skill/agent directory and file names
// (e.g. "adversarial-prompt-testing"). Used as a fallback resolver: listSkills
// / listAgents return both an ID (the real directory name) and a Name (the
// frontmatter `name:` field, or a Title-Cased fallback derived from the ID)
// - callers naturally sometimes pass Name back into loadSkill/loadAgent
// instead of ID. sanitizeString alone only strips characters, it does not
// normalize case or spacing, so a Name like that resolves to a squished
// PascalCase string that never matches any real directory ("item not found").
func slugify(s string) string {
	s = strings.ToLower(s)
	reg, _ := regexp.Compile(`[^a-z0-9]+`)
	s = reg.ReplaceAllString(s, "-")
	return strings.Trim(s, "-")
}

// resolveDirName picks the actual on-disk directory name for an item under
// parent, given a caller-supplied name that may be the literal ID (already
// sanitized) or a pretty display Name. Tries the literal sanitized form
// first (preserves existing behavior/error messages when it's already
// correct), then falls back to the slugified form. Returns the sanitized
// literal unchanged if neither resolves, so callers get the same
// "item not found at <path>" error as before.
func resolveDirName(parent, name string) string {
	literal := sanitizeString(name)
	if _, err := os.Stat(filepath.Join(parent, literal)); err == nil {
		return literal
	}
	if slug := slugify(name); slug != "" && slug != literal {
		if _, err := os.Stat(filepath.Join(parent, slug)); err == nil {
			return slug
		}
	}
	return literal
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
			names = append(names, strings.TrimSuffix(e.Name(), ".md"))
		}
	}
	return mcp.NewToolResultText(strings.Join(names, "\n")), nil
}

func parseFrontmatter(content string) map[string]string {
	meta := make(map[string]string)
	// Match YAML-style frontmatter or simple markdown headers
	re := regexp.MustCompile(`(?s)^---\s*\n(.*?)\n---`)
	match := re.FindStringSubmatch(content)
	if len(match) > 1 {
		lines := strings.Split(match[1], "\n")
		for _, line := range lines {
			parts := strings.SplitN(line, ":", 2)
			if len(parts) == 2 {
				key := strings.TrimSpace(parts[0])
				val := strings.TrimSpace(parts[1])
				// Strip quotes if present
				val = strings.Trim(val, `"'`)
				meta[key] = val
			}
		}
	} else {
		// Fallback: extract first H1 as name and first paragraph as description
		h1Re := regexp.MustCompile(`(?m)^#\s+(.+)$`)
		if h1Match := h1Re.FindStringSubmatch(content); len(h1Match) > 1 {
			meta["name"] = h1Match[1]
		}
	}
	return meta
}
