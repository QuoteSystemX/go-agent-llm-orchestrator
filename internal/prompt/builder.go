package prompt

import (
	"bytes"
	_ "embed"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"text/template"

	"go-agent-llm-orchestrator/internal/db"
)

//go:embed session.md
var defaultSessionTemplate string

//go:embed audit.md
var defaultAuditTemplate string

//go:embed red_team.md
var defaultRedTeamTemplate string

//go:embed system.md
var defaultSystemTemplate string

type Data struct {
	Agent              string
	Mission            string
	Pattern            string
	Command            string
	AgentProfile       string
	WorkflowProtocol   string
	PatternMethodology string
	RagContext         string
	
	// For service prompts
	Context string
	Proposal string
}

// Builder reads pattern and agent files from a local prompt-library clone.
type Builder struct {
	db                  *db.DB
	libraryDir          string
	cachedPatternsPath  string
	cachedAgentsPath    string
	cachedWorkflowsPath string
	cachedPromptsPath   string
}

func NewBuilder(database *db.DB, libraryDir string) *Builder {
	return &Builder{db: database, libraryDir: libraryDir}
}

func (b *Builder) IsReady() bool {
	_, err := os.Stat(filepath.Join(b.libraryDir, "prompt", "patterns"))
	return err == nil
}

// GetServicePrompt loads a service prompt from the library or returns the default.
func (b *Builder) GetServicePrompt(name string, data any) (string, error) {
	if b.cachedPromptsPath == "" {
		b.cachedPromptsPath = b.db.GetSetting("prompt_library_service_prompts_path", ".agent/prompts")
	}

	path := filepath.Join(b.libraryDir, b.cachedPromptsPath, name+".md")
	content := ""

	if b.IsReady() {
		if c, err := os.ReadFile(path); err == nil {
			content = string(c)
		}
	}

	if content == "" {
		switch name {
		case "audit":
			content = defaultAuditTemplate
		case "red_team":
			content = defaultRedTeamTemplate
		case "system":
			content = defaultSystemTemplate
		case "session":
			content = defaultSessionTemplate
		default:
			return "", fmt.Errorf("unknown service prompt: %s", name)
		}
	}

	tmpl, err := template.New(name).Parse(content)
	if err != nil {
		return "", err
	}

	var buf bytes.Buffer
	if err := tmpl.Execute(&buf, data); err != nil {
		return "", err
	}
	return buf.String(), nil
}

func (b *Builder) HasPrompt(agent, pattern, mission string) bool {
	if !b.IsReady() {
		return false
	}

	if b.cachedAgentsPath == "" {
		b.cachedAgentsPath = b.db.GetSetting("prompt_library_agents_path", ".agent/agents")
	}
	if _, err := os.Stat(filepath.Join(b.libraryDir, b.cachedAgentsPath, agent+".md")); err == nil {
		return true
	}

	if pattern != "" && pattern != "none" {
		if b.cachedPatternsPath == "" {
			b.cachedPatternsPath = b.db.GetSetting("prompt_library_patterns_path", "prompt/patterns")
		}
		if _, err := os.Stat(filepath.Join(b.libraryDir, b.cachedPatternsPath, pattern+".md")); err == nil {
			return true
		}
	}

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

func (b *Builder) Build(agent, pattern, mission, ragContext string) (string, error) {
	d := &Data{
		Agent:      agent,
		Pattern:    pattern,
		Mission:    mission,
		RagContext: ragContext,
	}

	if b.cachedAgentsPath == "" {
		b.cachedAgentsPath = b.db.GetSetting("prompt_library_agents_path", ".agent/agents")
	}
	if content, err := os.ReadFile(filepath.Join(b.libraryDir, b.cachedAgentsPath, agent+".md")); err == nil {
		d.AgentProfile = string(content)
	}

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

	if b.cachedPatternsPath == "" {
		b.cachedPatternsPath = b.db.GetSetting("prompt_library_patterns_path", "prompt/patterns")
	}
	if content, err := os.ReadFile(filepath.Join(b.libraryDir, b.cachedPatternsPath, pattern+".md")); err == nil {
		d.PatternMethodology = string(content)
	}

	return b.GetServicePrompt("session", d)
}
