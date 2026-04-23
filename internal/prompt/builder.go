package prompt

import (
	"bytes"
	_ "embed"
	"os"
	"path/filepath"
	"strings"
	"text/template"

	"go-agent-llm-orchestrator/internal/db"
)

//go:embed session.md
var sessionTemplate string

var bmadPatterns = map[string]bool{
	"discovery":      true,
	"story_writer":   true,
	"sprint_planner": true,
	"full_cycle":     true,
	"sprint_closer":  true,
}

type Data struct {
	Agent              string
	Mission            string
	Pattern            string
	Command            string
	AgentProfile       string
	WorkflowProtocol   string
	PatternMethodology string
	IsBMAD             bool
}

// Builder reads pattern and agent files from a local prompt-library clone.
type Builder struct {
	db         *db.DB
	libraryDir string
}

func NewBuilder(database *db.DB, libraryDir string) *Builder {
	return &Builder{db: database, libraryDir: libraryDir}
}

// IsReady reports whether the library directory looks like a valid clone.
func (b *Builder) IsReady() bool {
	_, err := os.Stat(filepath.Join(b.libraryDir, "prompt", "patterns"))
	return err == nil
}

// HasPrompt reports whether the pattern file exists for the given pattern.
// Agent file is optional in Build(), so only the pattern is required.
func (b *Builder) HasPrompt(pattern string) bool {
	if !b.IsReady() || pattern == "" {
		return false
	}
	patternsPath := b.db.GetSetting("prompt_library_patterns_path", "prompt/patterns")
	_, err := os.Stat(filepath.Join(b.libraryDir, patternsPath, pattern+".md"))
	return err == nil
}

// Build assembles the full Jules prompt for a task.
func (b *Builder) Build(agent, pattern, mission string) (string, error) {
	d := &Data{
		Agent:   agent,
		Pattern: pattern,
		Mission: mission,
		IsBMAD:  bmadPatterns[pattern],
	}

	// Agent profile
	agentsPath := b.db.GetSetting("prompt_library_agents_path", ".agent/agents")
	if content, err := os.ReadFile(filepath.Join(b.libraryDir, agentsPath, agent+".md")); err == nil {
		d.AgentProfile = string(content)
	}

	// Workflow command (mission starts with "/command ...")
	if strings.HasPrefix(mission, "/") {
		parts := strings.SplitN(mission, " ", 2)
		d.Command = strings.TrimPrefix(parts[0], "/")
		workflowsPath := b.db.GetSetting("prompt_library_workflows_path", ".agent/workflows")
		wfPath := filepath.Join(b.libraryDir, workflowsPath, d.Command+".md")
		if content, err := os.ReadFile(wfPath); err == nil {
			d.WorkflowProtocol = string(content)
		}
	}

	// Pattern methodology
	patternsPath := b.db.GetSetting("prompt_library_patterns_path", "prompt/patterns")
	if content, err := os.ReadFile(filepath.Join(b.libraryDir, patternsPath, pattern+".md")); err == nil {
		d.PatternMethodology = string(content)
	}

	tmpl, err := template.New("session").Parse(sessionTemplate)
	if err != nil {
		return "", err
	}

	var buf bytes.Buffer
	if err := tmpl.Execute(&buf, d); err != nil {
		return "", err
	}
	return buf.String(), nil
}
