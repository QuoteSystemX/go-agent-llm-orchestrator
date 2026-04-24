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

// bmadPatterns is deprecated and removed as part of the architecture cleanup.

type Data struct {
	Agent              string
	Mission            string
	Pattern            string
	Command            string
	AgentProfile       string
	WorkflowProtocol   string
	PatternMethodology string
}

// Builder reads pattern and agent files from a local prompt-library clone.
type Builder struct {
	db                *db.DB
	libraryDir        string
	cachedPatternsPath string
	cachedAgentsPath   string
	cachedWorkflowsPath string
}

func NewBuilder(database *db.DB, libraryDir string) *Builder {
	return &Builder{db: database, libraryDir: libraryDir}
}

// IsReady reports whether the library directory looks like a valid clone.
func (b *Builder) IsReady() bool {
	_, err := os.Stat(filepath.Join(b.libraryDir, "prompt", "patterns"))
	return err == nil
}

// HasPrompt reports whether a valid prompt can be assembled for the given task.
// A prompt is considered ready if it has at least one of:
// 1. A valid agent profile in .agent/agents/
// 2. A valid methodology in prompt/patterns/
// 3. A valid workflow protocol for a command in the mission
func (b *Builder) HasPrompt(agent, pattern, mission string) bool {
	if !b.IsReady() {
		return false
	}

	// 1. Check agent profile
	if b.cachedAgentsPath == "" {
		b.cachedAgentsPath = b.db.GetSetting("prompt_library_agents_path", ".agent/agents")
	}
	if _, err := os.Stat(filepath.Join(b.libraryDir, b.cachedAgentsPath, agent+".md")); err == nil {
		return true
	}

	// 2. Check pattern methodology
	if pattern != "" && pattern != "none" {
		if b.cachedPatternsPath == "" {
			b.cachedPatternsPath = b.db.GetSetting("prompt_library_patterns_path", "prompt/patterns")
		}
		if _, err := os.Stat(filepath.Join(b.libraryDir, b.cachedPatternsPath, pattern+".md")); err == nil {
			return true
		}
	}

	// 3. Check workflow command
	if strings.HasPrefix(mission, "/") {
		cmd := b.ExtractCommand(mission)
		if cmd != "" {
			if b.cachedWorkflowsPath == "" {
				b.cachedWorkflowsPath = b.db.GetSetting("prompt_library_workflows_path", ".agent/workflows")
			}
			if _, err := os.Stat(filepath.Join(b.libraryDir, b.cachedWorkflowsPath, cmd+".md")); err == nil {
				return true
			}
		}
	}

	return false
}

func (b *Builder) ExtractCommand(mission string) string {
	if !strings.HasPrefix(mission, "/") {
		return ""
	}
	parts := strings.SplitN(mission, " ", 2)
	return strings.TrimPrefix(parts[0], "/")
}

// Build assembles the full Jules prompt for a task.
func (b *Builder) Build(agent, pattern, mission string) (string, error) {
	d := &Data{
		Agent:   agent,
		Pattern: pattern,
		Mission: mission,
	}

	// Agent profile
	if b.cachedAgentsPath == "" {
		b.cachedAgentsPath = b.db.GetSetting("prompt_library_agents_path", ".agent/agents")
	}
	if content, err := os.ReadFile(filepath.Join(b.libraryDir, b.cachedAgentsPath, agent+".md")); err == nil {
		d.AgentProfile = string(content)
	}

	// Workflow command (mission starts with "/command ...")
	if strings.HasPrefix(mission, "/") {
		parts := strings.SplitN(mission, " ", 2)
		d.Command = strings.TrimPrefix(parts[0], "/")
		if b.cachedWorkflowsPath == "" {
			b.cachedWorkflowsPath = b.db.GetSetting("prompt_library_workflows_path", ".agent/workflows")
		}
		wfPath := filepath.Join(b.libraryDir, b.cachedWorkflowsPath, d.Command+".md")
		if content, err := os.ReadFile(wfPath); err == nil {
			d.WorkflowProtocol = string(content)
		}
	}

	// Pattern methodology
	if b.cachedPatternsPath == "" {
		b.cachedPatternsPath = b.db.GetSetting("prompt_library_patterns_path", "prompt/patterns")
	}
	if content, err := os.ReadFile(filepath.Join(b.libraryDir, b.cachedPatternsPath, pattern+".md")); err == nil {
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
