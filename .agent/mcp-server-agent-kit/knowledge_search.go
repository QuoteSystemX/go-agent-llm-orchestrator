package main

import (
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
)

// This file replaces the previous exec.Command("python3", ...) call into
// .agent/scripts/knowledge/semantic_brain_engine.py, which was fatally
// broken two ways in the mcp-server-agent-kit distroless runtime image
// (tasks/done/2026-08-12-agent-kit-search-knowledge-broken.md):
//   1. the constructed script path was missing a "knowledge/" path segment
//      and never resolved to the real file even on a host with python3;
//   2. the runtime image is `gcr.io/distroless/static:nonroot` — no shell,
//      no python3, no package manager — so exec.Command("python3", ...)
//      could never succeed there regardless of the path.
// The logic below is a Go port of semantic_brain_engine.py's
// search_lessons/calculate_similarity/preprocess — same weighted
// Jaccard-like token-overlap scoring over "## "/"### "-delimited sections
// of the global cross-project lessons file, kept behaviorally equivalent
// so existing callers see the same ranking, just embedded in the binary
// instead of shelled out.

// lessonMatch is one scored section of the global lessons file.
type lessonMatch struct {
	Content string
	Score   float64
}

// keywordWeight mirrors semantic_brain_engine.py's calculate_similarity
// weights table — technical terms score higher than an incidental word
// match. Tokens not listed here default to weight 1.0.
var keywordWeight = map[string]float64{
	"memory": 2.0, "leak": 2.0, "deadlock": 2.5, "security": 2.5,
	"api": 1.5, "database": 1.5, "performance": 2.0, "slow": 1.5,
	"concurrency": 2.0, "race": 2.0, "auth": 2.5, "token": 1.5,
}

var nonAlnumSpace = regexp.MustCompile(`[^a-z0-9\s]`)

// preprocessTokens lowercases, strips punctuation, and returns the unique
// whitespace-separated tokens — a Go port of semantic_brain_engine.py's
// preprocess() (which also dedupes via `set()`).
func preprocessTokens(text string) []string {
	cleaned := nonAlnumSpace.ReplaceAllString(strings.ToLower(text), "")
	fields := strings.Fields(cleaned)
	seen := make(map[string]struct{}, len(fields))
	unique := make([]string, 0, len(fields))
	for _, f := range fields {
		if _, ok := seen[f]; ok {
			continue
		}
		seen[f] = struct{}{}
		unique = append(unique, f)
	}
	return unique
}

// calculateSimilarity is a Go port of semantic_brain_engine.py's
// calculate_similarity: weighted keyword-overlap score, normalized by the
// (deduped) query token count.
func calculateSimilarity(queryTokens, targetTokens []string) float64 {
	if len(queryTokens) == 0 || len(targetTokens) == 0 {
		return 0
	}
	targetSet := make(map[string]struct{}, len(targetTokens))
	for _, t := range targetTokens {
		targetSet[t] = struct{}{}
	}
	var score float64
	for _, q := range queryTokens {
		if _, ok := targetSet[q]; !ok {
			continue
		}
		if w, ok := keywordWeight[q]; ok {
			score += w
		} else {
			score += 1.0
		}
	}
	return score / (float64(len(queryTokens)) + 0.1)
}

// splitLessonSections splits lessons_learned.md content into sections,
// starting a new section at each line beginning with "##" or "###" (a Go
// port of Python's re.split(r'\n(?=##|###)', content), which RE2's lack of
// lookahead support rules out doing with a single regexp.Split call — a
// line must START with "##"/"###" to open a new section, and the very
// first line never splits even if it qualifies, matching the lookahead's
// requirement of a preceding newline to consume).
func splitLessonSections(content string) []string {
	lines := strings.Split(content, "\n")
	var sections []string
	current := make([]string, 0, len(lines))
	for i, line := range lines {
		if i > 0 && strings.HasPrefix(line, "##") {
			sections = append(sections, strings.Join(current, "\n"))
			current = current[:0]
		}
		current = append(current, line)
	}
	sections = append(sections, strings.Join(current, "\n"))
	return sections
}

// resolveGlobalLessonsPath mirrors lib/paths.py's GLOBAL_LESSONS_PATH:
// $AGENT_GLOBAL_ROOT/lessons_learned.md, defaulting to
// ~/.agent_knowledge/lessons_learned.md — the cross-project, cross-repo
// knowledge base (distinct from this repo's own .agent/KNOWLEDGE.md).
func resolveGlobalLessonsPath() string {
	root := os.Getenv("AGENT_GLOBAL_ROOT")
	if root == "" {
		home, err := os.UserHomeDir()
		if err != nil {
			home = "."
		}
		return filepath.Join(home, ".agent_knowledge", "lessons_learned.md")
	}
	if strings.HasPrefix(root, "~") {
		if home, err := os.UserHomeDir(); err == nil {
			root = filepath.Join(home, strings.TrimPrefix(root, "~"))
		}
	}
	return filepath.Join(root, "lessons_learned.md")
}

// searchGlobalLessons scores every section of the global lessons file
// against query and returns the top matches, highest score first. A
// missing lessons file is not an error — it returns no matches, same as
// semantic_brain_engine.py's search_lessons() early-return.
func searchGlobalLessons(query string, topN int) []lessonMatch {
	data, err := os.ReadFile(resolveGlobalLessonsPath())
	if err != nil {
		return nil
	}
	queryTokens := preprocessTokens(query)
	var matches []lessonMatch
	for _, section := range splitLessonSections(string(data)) {
		score := calculateSimilarity(queryTokens, preprocessTokens(section))
		if score <= 0 {
			continue
		}
		matches = append(matches, lessonMatch{Content: strings.TrimSpace(section), Score: score})
	}
	sort.SliceStable(matches, func(i, j int) bool { return matches[i].Score > matches[j].Score })
	if len(matches) > topN {
		matches = matches[:topN]
	}
	return matches
}
