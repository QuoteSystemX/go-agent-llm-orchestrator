package main

import (
	"bufio"
	"bytes"
	"context"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"unicode/utf8"
)

// This file implements the sandboxed, read-only tool set (read_file, grep)
// given to call_agent-dispatched sub-agent personas so they can check a
// claim about the codebase before making it, instead of confabulating a
// plausible-sounding file path or symbol. See executeOllamaToolLoop
// (executor.go) for the loop that drives these against Ollama's
// OpenAI-compatible /api/chat function-calling format.
//
// Scope note (L4 Council/Arena review, 2026-08-14): these tools deliberately
// do NOT do content-level secret scanning. Within workspaceRoot, the
// orchestrator dispatching these personas already has unrestricted read
// access to every file here — invokeAgent used to require the orchestrator
// to manually paste file content into the sub-agent prompt, so a persona
// reading a file itself crosses no new trust boundary. The secret-glob
// refusal below is cheap insurance against a persona accidentally quoting a
// well-known secret filename's content, not a defense of a boundary that
// doesn't exist here. The boundary that DOES matter — and is enforced below
// — is workspaceRoot containment itself: reading outside it (sibling
// projects, /etc/passwd, etc.) is a real escalation.

// secretGlobs are common secret-bearing filename patterns, refused by both
// tools regardless of path validity. Matching is on the base filename only,
// case-insensitive.
var secretGlobs = []string{
	".env", ".env.*", "*.pem", "*.key", "id_rsa*", "id_ed25519*", "id_ecdsa*",
	"*.p12", "*.pfx", "*.crt", "*.cer", "*.gpg", "*.asc", "*credentials*",
	"*.token", "*_rsa", "*.ppk", "*.jks", "*.keystore",
}

// skipGrepDirs are directory names grep never descends into — VCS internals
// and dependency/build trees, not project source. Deliberately does NOT
// include a blanket "any dot-prefixed directory" rule: this project's own
// convention keeps real source under dot-directories (.agent/, .claude/),
// and a persona is often specifically asked about code that lives there.
var skipGrepDirs = map[string]bool{
	".git":         true,
	"node_modules": true,
	"vendor":       true,
	".cache":       true,
	"__pycache__":  true,
	"dist":         true,
	"build":        true,
}

// isSecretPath reports whether realPath's base filename matches a
// secret-bearing glob. ".pub" files are exempted even if the stem matches an
// SSH private-key pattern (id_rsa*, id_ed25519*, ...) — the public half of a
// keypair is meant to be public, and id_rsa.pub would otherwise be refused
// by the same wildcard that correctly refuses id_rsa itself.
func isSecretPath(realPath string) bool {
	base := strings.ToLower(filepath.Base(realPath))
	if strings.HasSuffix(base, ".pub") {
		return false
	}
	for _, pat := range secretGlobs {
		if ok, _ := filepath.Match(strings.ToLower(pat), base); ok {
			return true
		}
	}
	return false
}

// truncateAtRuneBoundary trims s to at most maxBytes bytes without splitting
// a multi-byte UTF-8 rune. Naive byte-index slicing (s[:n]) can land inside
// a multi-byte character — this codebase's own files contain Cyrillic text
// and emoji — producing invalid UTF-8 that json.Marshal silently mangles
// into U+FFFD replacement characters in the tool result sent back to the
// model.
func truncateAtRuneBoundary(s string, maxBytes int) string {
	if maxBytes <= 0 || len(s) <= maxBytes {
		return s
	}
	b := s[:maxBytes]
	// A byte can be a valid rune-start byte (utf8.RuneStart) while still
	// being an INCOMPLETE encoding if the cut lands right after it, before
	// its continuation bytes — e.g. truncating "п" (0xD0 0xBF) to just
	// "\xD0" leaves a valid start byte with no continuation. Decode from the
	// end and keep trimming one byte at a time until the trailing rune
	// decodes cleanly (or the string is empty).
	for len(b) > 0 {
		r, size := utf8.DecodeLastRuneInString(b)
		if r != utf8.RuneError || size != 1 {
			break
		}
		b = b[:len(b)-1]
	}
	return b
}

// coerceIntArg reads args[name] as an int whether the model sent it as a
// native JSON number or — defensively, mirroring the string-fallback
// already applied to the top-level tool-call arguments object in
// executeOllamaToolLoop — a numeric string. Returns 0 if absent or
// unparseable.
func coerceIntArg(args map[string]any, name string) int {
	switch v := args[name].(type) {
	case float64:
		return int(v)
	case string:
		if n, err := strconv.Atoi(strings.TrimSpace(v)); err == nil {
			return n
		}
	}
	return 0
}

// resolveSandboxedPath resolves relPath against workspaceRoot and rejects any
// result that escapes the sandbox — via ".." traversal or a symlink pointing
// outside workspaceRoot. Both workspaceRoot and the target are run through
// filepath.EvalSymlinks so a symlinked workspace root itself (common in dev
// setups) doesn't produce a false-positive rejection.
//
// This resolve-then-open pattern narrows, but does not fully eliminate, a
// TOCTOU race against a symlink swapped after this check and before the
// caller opens the file — fully closing that needs platform-specific
// openat2(RESOLVE_BENEATH), out of scope for a pure-stdlib implementation.
// Documented here as a known residual limitation rather than silently
// assumed away.
func resolveSandboxedPath(workspaceRoot, relPath string) (string, error) {
	if relPath == "" {
		return "", fmt.Errorf("path is required")
	}
	if strings.ContainsRune(relPath, 0) {
		return "", fmt.Errorf("invalid path")
	}
	if filepath.IsAbs(relPath) {
		return "", fmt.Errorf("path must be relative to the workspace root, got absolute path %q", relPath)
	}

	cleanedRoot := filepath.Clean(workspaceRoot)
	joined := filepath.Join(cleanedRoot, relPath)

	// Lexical check first — catches ".." escapes even before touching the filesystem.
	rel, err := filepath.Rel(cleanedRoot, joined)
	if err != nil || rel == ".." || strings.HasPrefix(rel, ".."+string(filepath.Separator)) {
		return "", fmt.Errorf("path %q resolves outside the workspace root", relPath)
	}

	realRoot, err := filepath.EvalSymlinks(cleanedRoot)
	if err != nil {
		return "", fmt.Errorf("cannot resolve workspace root: %w", err)
	}
	realTarget, err := filepath.EvalSymlinks(joined)
	if err != nil {
		return "", fmt.Errorf("cannot resolve %q: %w", relPath, err)
	}

	relReal, err := filepath.Rel(realRoot, realTarget)
	if err != nil || relReal == ".." || strings.HasPrefix(relReal, ".."+string(filepath.Separator)) {
		return "", fmt.Errorf("path %q resolves outside the workspace root (symlink escape)", relPath)
	}

	return realTarget, nil
}

// grepIndexEntry is one file collected by toolBudget.grepIndexFor.
type grepIndexEntry struct {
	relPath string
	content []byte
}

// toolBudget bounds a single invokeAgent dispatch's tool usage: total call
// count AND cumulative bytes returned (a call-count-only budget is defeated
// by chunked line-range reads — flagged independently by the L4
// penetration-tester and security-auditor reviews). It also caches grep's
// file walk for the lifetime of one dispatch — up to MaxToolCalls greps in
// the same dispatch would otherwise re-walk and re-read the same directory
// tree from scratch every time (flagged by the efficiency review).
type toolBudget struct {
	cfg       SubAgentToolsConfig
	callsUsed int
	bytesUsed int
	grepIndex map[string][]grepIndexEntry // keyed by resolved scope path
}

func newToolBudget(cfg SubAgentToolsConfig) *toolBudget {
	return &toolBudget{cfg: cfg.resolved()}
}

// reserveCall enforces the per-dispatch tool-call count budget.
func (tb *toolBudget) reserveCall() error {
	if tb.callsUsed >= tb.cfg.MaxToolCalls {
		return fmt.Errorf("tool-call budget exhausted (%d/%d calls used this dispatch)", tb.callsUsed, tb.cfg.MaxToolCalls)
	}
	tb.callsUsed++
	return nil
}

// reserveBytes enforces the cumulative per-dispatch byte ceiling, independent
// of the per-call byte cap.
func (tb *toolBudget) reserveBytes(n int) error {
	if tb.bytesUsed+n > tb.cfg.MaxBytesPerDispatch {
		return fmt.Errorf("per-dispatch byte budget exhausted (%d/%d bytes used, this read would add %d)", tb.bytesUsed, tb.cfg.MaxBytesPerDispatch, n)
	}
	tb.bytesUsed += n
	return nil
}

func (tb *toolBudget) exceeded() bool {
	return tb.callsUsed >= tb.cfg.MaxToolCalls || tb.bytesUsed >= tb.cfg.MaxBytesPerDispatch
}

// grepIndexFor returns the walked file list (path + content) for scopeReal,
// building and caching it on first use within this dispatch. realRoot is
// used only to compute each entry's repo-relative display path.
func (tb *toolBudget) grepIndexFor(ctx context.Context, scopeReal, realRoot string) ([]grepIndexEntry, error) {
	if tb.grepIndex == nil {
		tb.grepIndex = make(map[string][]grepIndexEntry)
	}
	if cached, ok := tb.grepIndex[scopeReal]; ok {
		return cached, nil
	}

	var entries []grepIndexEntry
	walkErr := filepath.WalkDir(scopeReal, func(path string, d fs.DirEntry, err error) error {
		if ctx.Err() != nil {
			return ctx.Err()
		}
		if err != nil {
			return nil // skip unreadable entries rather than aborting the whole search
		}
		if d.IsDir() {
			// Skip VCS internals and dependency trees only — NOT every
			// dot-prefixed directory. Repos in this project's own style keep
			// real source under dot-directories (.agent/, .claude/, .github/),
			// so a blanket dot-directory skip would make grep blind to the
			// exact kind of code a persona is most likely to be asked about.
			if path != scopeReal && skipGrepDirs[d.Name()] {
				return filepath.SkipDir
			}
			return nil
		}
		if isSecretPath(path) {
			return nil
		}
		info, err := d.Info()
		if err != nil || info.Size() > 1<<20 { // 1MB — grep is for targeted verification, not indexing
			return nil
		}
		data, err := os.ReadFile(path)
		if err != nil || looksBinary(data) {
			return nil
		}
		relToRoot, err := filepath.Rel(realRoot, path)
		if err != nil {
			relToRoot = path
		}
		entries = append(entries, grepIndexEntry{relPath: relToRoot, content: data})
		return nil
	})
	if walkErr != nil {
		return nil, fmt.Errorf("grep failed: %w", walkErr)
	}

	tb.grepIndex[scopeReal] = entries
	return entries, nil
}

// readFileTool reads relPath (relative to workspaceRoot), optionally
// restricted to a 1-indexed inclusive [startLine, endLine] range. Files
// larger than the per-call byte cap must be read via a line range rather
// than in full. Line-range reads stream the file with bufio.Scanner instead
// of loading it whole, so a request for a handful of lines near the start of
// a large file doesn't pull the entire file into memory — bounded further by
// hardScanCeiling below regardless of the requested range.
func readFileTool(ctx context.Context, workspaceRoot string, budget *toolBudget, relPath string, startLine, endLine int) (string, error) {
	real, err := resolveSandboxedPath(workspaceRoot, relPath)
	if err != nil {
		return "", err
	}
	if isSecretPath(real) {
		return "", fmt.Errorf("refusing to read %q — matches a secret-bearing file pattern", relPath)
	}
	info, err := os.Stat(real)
	if err != nil {
		return "", fmt.Errorf("cannot stat %q: %w", relPath, err)
	}
	if info.IsDir() {
		return "", fmt.Errorf("%q is a directory, not a file", relPath)
	}

	if startLine <= 0 && endLine <= 0 {
		if int(info.Size()) > budget.cfg.MaxBytesPerCall {
			return "", fmt.Errorf("%q is %d bytes, larger than the %d-byte per-call cap — request a line range instead of the whole file", relPath, info.Size(), budget.cfg.MaxBytesPerCall)
		}
		data, err := os.ReadFile(real)
		if err != nil {
			return "", fmt.Errorf("cannot read %q: %w", relPath, err)
		}
		if err := budget.reserveBytes(len(data)); err != nil {
			return "", err
		}
		return string(data), nil
	}

	if startLine <= 0 {
		startLine = 1
	}
	if endLine > 0 && startLine > endLine {
		return "", fmt.Errorf("start_line (%d) must be <= end_line (%d)", startLine, endLine)
	}

	const hardScanCeiling = 20 * 1024 * 1024 // 20MB — bounds worst-case scan latency even for a narrow line range
	if info.Size() > hardScanCeiling {
		return "", fmt.Errorf("%q is %d bytes, too large to scan even for a line-range read (%d-byte ceiling)", relPath, info.Size(), hardScanCeiling)
	}

	f, err := os.Open(real)
	if err != nil {
		return "", fmt.Errorf("cannot read %q: %w", relPath, err)
	}
	defer f.Close()

	scanner := bufio.NewScanner(f)
	scanner.Buffer(make([]byte, 64*1024), 1024*1024) // allow lines up to 1MB
	var collected []string
	lineNo := 0
	for scanner.Scan() {
		if ctx.Err() != nil {
			return "", ctx.Err()
		}
		lineNo++
		if lineNo < startLine {
			continue
		}
		if endLine > 0 && lineNo > endLine {
			break
		}
		collected = append(collected, scanner.Text())
	}
	if err := scanner.Err(); err != nil {
		return "", fmt.Errorf("cannot read %q: %w", relPath, err)
	}
	if lineNo < startLine {
		return "", fmt.Errorf("start_line %d exceeds file length (%d lines)", startLine, lineNo)
	}

	slice := strings.Join(collected, "\n")
	if len(slice) > budget.cfg.MaxBytesPerCall {
		slice = truncateAtRuneBoundary(slice, budget.cfg.MaxBytesPerCall) + fmt.Sprintf("\n…[truncated at %d-byte per-call cap]", budget.cfg.MaxBytesPerCall)
	}
	if err := budget.reserveBytes(len(slice)); err != nil {
		return "", err
	}
	return slice, nil
}

// grepTool searches text files under workspaceRoot (or a relative subpath
// scope) for a regular expression, for verifying a specific claim rather
// than open-ended exploration — results are capped. Go's regexp package is
// RE2-based: linear-time by construction, so it has no catastrophic-
// backtracking ReDoS surface regardless of the pattern a persona supplies.
// The underlying file walk/read is cached per dispatch via budget.grepIndexFor
// — repeated greps in the same dispatch reuse it instead of re-walking.
func grepTool(ctx context.Context, workspaceRoot string, budget *toolBudget, pattern, scope string) (string, error) {
	if pattern == "" {
		return "", fmt.Errorf("pattern is required")
	}
	re, err := regexp.Compile(pattern)
	if err != nil {
		return "", fmt.Errorf("invalid pattern: %w", err)
	}

	realRoot, err := filepath.EvalSymlinks(filepath.Clean(workspaceRoot))
	if err != nil {
		return "", fmt.Errorf("cannot resolve workspace root: %w", err)
	}

	scopeReal := realRoot
	if scope != "" && scope != "." {
		r, err := resolveSandboxedPath(workspaceRoot, scope)
		if err != nil {
			return "", err
		}
		scopeReal = r
	}

	entries, err := budget.grepIndexFor(ctx, scopeReal, realRoot)
	if err != nil {
		return "", err
	}

	var matches []string
	maxMatches := budget.cfg.MaxGrepMatches
	for _, entry := range entries {
		if ctx.Err() != nil {
			return "", ctx.Err()
		}
		if len(matches) >= maxMatches {
			break
		}
		for lineNo, line := range strings.Split(string(entry.content), "\n") {
			if len(matches) >= maxMatches {
				break
			}
			if re.MatchString(line) {
				trimmed := strings.TrimSpace(line)
				if len(trimmed) > 300 {
					trimmed = truncateAtRuneBoundary(trimmed, 300) + "…"
				}
				matches = append(matches, fmt.Sprintf("%s:%d: %s", entry.relPath, lineNo+1, trimmed))
			}
		}
	}

	if len(matches) == 0 {
		return "no matches found", nil
	}
	result := strings.Join(matches, "\n")
	if len(result) > budget.cfg.MaxBytesPerCall {
		result = truncateAtRuneBoundary(result, budget.cfg.MaxBytesPerCall) + "\n…[truncated at per-call byte cap]"
	}
	if err := budget.reserveBytes(len(result)); err != nil {
		return "", err
	}
	return result, nil
}

func looksBinary(data []byte) bool {
	n := len(data)
	if n > 512 {
		n = 512
	}
	return bytes.IndexByte(data[:n], 0) != -1
}

// buildReadOnlyToolDefs returns the read_file/grep tool definitions in
// Ollama's OpenAI-compatible function-calling format (distinct from the
// Anthropic tool format executeAgenticLoop uses for Jan — see
// executeOllamaToolLoop).
func buildReadOnlyToolDefs() []map[string]any {
	return []map[string]any{
		{
			"type": "function",
			"function": map[string]any{
				"name":        "read_file",
				"description": "Read a file from the current repository to verify a claim before stating it. Path is relative to the repository root. For files larger than ~32KB, pass start_line/end_line instead of omitting them.",
				"parameters": map[string]any{
					"type": "object",
					"properties": map[string]any{
						"path":       map[string]any{"type": "string", "description": `File path relative to the repository root, e.g. "internal/model/issue.go".`},
						"start_line": map[string]any{"type": "integer", "description": "Optional 1-indexed first line to read."},
						"end_line":   map[string]any{"type": "integer", "description": "Optional 1-indexed last line to read (inclusive)."},
					},
					"required": []string{"path"},
				},
			},
		},
		{
			"type": "function",
			"function": map[string]any{
				"name":        "grep",
				"description": "Search files in the current repository for a regular expression, to verify a specific claim (e.g. does this function/path actually exist). Not for open-ended exploration — results are capped.",
				"parameters": map[string]any{
					"type": "object",
					"properties": map[string]any{
						"pattern": map[string]any{"type": "string", "description": "Regular expression to search for (RE2 syntax)."},
						"path":    map[string]any{"type": "string", "description": "Optional subdirectory to scope the search to, relative to the repository root. Defaults to the whole repository."},
					},
					"required": []string{"pattern"},
				},
			},
		},
	}
}

// runReadOnlyTool dispatches a single tool call by name, enforcing the
// per-dispatch call budget before doing any work. ctx is threaded down into
// readFileTool/grepTool so a slow scan/walk observes the surrounding
// dispatch's cancellation/timeout instead of running to completion regardless.
func (b *BrokerServer) runReadOnlyTool(ctx context.Context, name string, args map[string]any, budget *toolBudget) (string, error) {
	if err := budget.reserveCall(); err != nil {
		return "", err
	}
	switch name {
	case "read_file":
		path, _ := args["path"].(string)
		startLine := coerceIntArg(args, "start_line")
		endLine := coerceIntArg(args, "end_line")
		return readFileTool(ctx, b.workspaceRoot, budget, path, startLine, endLine)
	case "grep":
		pattern, _ := args["pattern"].(string)
		scope, _ := args["path"].(string)
		return grepTool(ctx, b.workspaceRoot, budget, pattern, scope)
	default:
		return "", fmt.Errorf("unknown tool %q — only read_file and grep are available", name)
	}
}
