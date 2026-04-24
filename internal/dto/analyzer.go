package dto

import (
	"context"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"os"
	"path/filepath"
	"strings"
	"time"

	"go-agent-llm-orchestrator/internal/db"
	"go-agent-llm-orchestrator/internal/llm"
	"go-agent-llm-orchestrator/internal/prompt"
)

type Analyzer struct {
	db            *db.DB
	router        *llm.Router
	promptBuilder *prompt.Builder
}

func NewAnalyzer(database *db.DB, router *llm.Router, promptBuilder *prompt.Builder) *Analyzer {
	return &Analyzer{
		db:            database,
		router:        router,
		promptBuilder: promptBuilder,
	}
}

type Proposal struct {
	Pattern    string `json:"pattern"`
	Agent      string `json:"agent"`
	Mission    string `json:"mission"`
	Schedule   string `json:"schedule"`
	Importance int    `json:"importance"`
	Category   string `json:"category"`
	Reason     string `json:"reason"`
}

type AnalysisResult struct {
	Proposals    []Proposal `json:"proposals"`
	CurrentStage string     `json:"current_stage"` // discovery, prd, architecture, stories, sprint, worker, closure
	Progress     int        `json:"progress"`      // 0-100%
}

func (a *Analyzer) AnalyzeRepo(ctx context.Context, repoName string) (*AnalysisResult, error) {
	basePath := a.db.GetSetting("repo_base_path", "./repos")
	repoPath := filepath.Join(basePath, repoName)

	// 1. Gather repository intel
	readme, _ := a.readFile(filepath.Join(repoPath, "README.md"))
	wiki, _ := a.readDir(filepath.Join(repoPath, "wiki"), ".md")
	
	// Check for .agent folder (BMAD context)
	agentContext := ""
	if _, err := os.Stat(filepath.Join(repoPath, ".agent")); err == nil {
		workflows, _ := a.readDir(filepath.Join(repoPath, ".agent", "workflows"), ".md")
		skills, _ := a.readDir(filepath.Join(repoPath, ".agent", "skills"), ".md")
		knowledge, _ := a.readFile(filepath.Join(repoPath, ".agent", "KNOWLEDGE.md"))
		arch, _ := a.readFile(filepath.Join(repoPath, ".agent", "ARCHITECTURE.md"))
		
		agentContext = fmt.Sprintf("### Repository .agent Context\nWorkflows:\n%s\nSkills:\n%s\nKnowledge:\n%s\nArchitecture:\n%s\n", 
			workflows, skills, knowledge, arch)
	}

	// Get current tasks for this repo
	currentTasks, _ := a.db.GetTasksByRepo(ctx, repoName)
	
	// Get templates (ConfigMap/DB workflows)
	templates, _ := NewTemplateManager(a.db).ListTemplates(ctx)
	
	// 2. Build prompt
	prompt := a.buildAnalysisPrompt(repoName, readme, wiki, agentContext, currentTasks, templates)
	
	// 3. Call LLM
	response, err := a.router.GenerateResponse(ctx, llm.Complex, prompt)
	if err != nil {
		return nil, err
	}
	
	// 4. Parse response (expecting markdown-wrapped JSON or just JSON)
	return a.parseAnalysisResult(response)
}

func (a *Analyzer) readFile(path string) (string, error) {
	data, err := ioutil.ReadFile(path)
	if err != nil {
		return "", err
	}
	return string(data), nil
}

func (a *Analyzer) readDir(path string, ext string) (string, error) {
	files, err := ioutil.ReadDir(path)
	if err != nil {
		return "", err
	}
	var content strings.Builder
	for _, f := range files {
		if !f.IsDir() && filepath.Ext(f.Name()) == ext {
			data, _ := ioutil.ReadFile(filepath.Join(path, f.Name()))
			content.WriteString(fmt.Sprintf("File: %s\n%s\n---\n", f.Name(), string(data)))
		}
	}
	return content.String(), nil
}

func (a *Analyzer) buildAnalysisPrompt(repoName string, readme string, wiki string, agentContext string, currentTasks []map[string]any, templates []Template) string {
	var sb strings.Builder
	sb.WriteString(fmt.Sprintf("Analyze the repository '%s' and propose tasks following the BMAD (Build, Monitor, Analyze, Deploy) methodology.\n\n", repoName))
	
	if readme != "" {
		sb.WriteString("### README.md\n")
		sb.WriteString(readme)
		sb.WriteString("\n\n")
	}
	
	if wiki != "" {
		sb.WriteString("### Wiki Content\n")
		sb.WriteString(wiki)
		sb.WriteString("\n\n")
	}

	if agentContext != "" {
		sb.WriteString(agentContext)
		sb.WriteString("\n")
	}
	
	sb.WriteString("### Current Tasks\n")
	for _, t := range currentTasks {
		sb.WriteString(fmt.Sprintf("- %s: %s (Pattern: %s)\n", t["id"], t["mission"], t["pattern"]))
	}
	sb.WriteString("\n")
	
	sb.WriteString("### Available Templates\n")
	for _, t := range templates {
		sb.WriteString(fmt.Sprintf("- Template: %s\n%s\n---\n", t.Name, t.Content))
	}
	sb.WriteString("\n")
	
	sb.WriteString("Your goal: Propose 3-5 new tasks or updates. Focus on the FULL BMAD methodology cycle:\n")
	sb.WriteString("1. Planning: /discovery -> /prd -> /architecture -> /stories -> /sprint\n")
	sb.WriteString("2. Execution: Worker tasks (implementing features/fixes)\n")
	sb.WriteString("3. Maintenance: /sprint-closer and Wiki/Docs actualization.\n\n")
	sb.WriteString("Critical priority: Service tasks (Wiki updates, Docs) MUST have high importance if they are lagging behind the worker tasks.\n\n")
	sb.WriteString("Return ONLY a JSON object with fields:\n")
	sb.WriteString("- current_stage: string (one of: discovery, prd, architecture, stories, sprint, worker, closure)\n")
	sb.WriteString("- progress: number (0-100)\n")
	sb.WriteString("- proposals: array of objects (pattern, agent, mission, schedule, importance, category, reason)\n")
	
	return sb.String()
}

func (a *Analyzer) parseAnalysisResult(response string) (*AnalysisResult, error) {
	// Simple JSON extraction from markdown
	jsonStr := response
	if start := strings.Index(response, "{"); start != -1 {
		if end := strings.LastIndex(response, "}"); end != -1 {
			jsonStr = response[start : end+1]
		}
	}
	
	var result AnalysisResult
	if err := json.Unmarshal([]byte(jsonStr), &result); err != nil {
		// Fallback to array parsing for backward compatibility with old prompts
		var proposals []Proposal
		if err2 := json.Unmarshal([]byte(jsonStr), &proposals); err2 == nil {
			return &AnalysisResult{Proposals: proposals}, nil
		}
		return nil, fmt.Errorf("failed to parse analysis result: %w\nResponse: %s", err, response)
	}
	return &result, nil
}

func (a *Analyzer) StartBackgroundLoop(ctx context.Context) {
	ticker := time.NewTicker(24 * time.Hour)
	defer ticker.Stop()

	// Run initial analysis after 1 minute to not block startup
	time.AfterFunc(1*time.Minute, func() {
		a.runScheduledAnalysis(ctx)
	})

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			a.runScheduledAnalysis(ctx)
		}
	}
}

func (a *Analyzer) runScheduledAnalysis(ctx context.Context) {
	repos, err := a.db.GetDistinctRepos(ctx)
	if err != nil {
		return
	}
	for _, repo := range repos {
		fmt.Printf("DTO: Running scheduled analysis for %s\n", repo)
		result, err := a.AnalyzeRepo(ctx, repo)
		if err != nil {
			fmt.Printf("DTO: Scheduled analysis failed for %s: %v\n", repo, err)
			continue
		}
		
		if len(result.Proposals) > 0 {
			fmt.Printf("DTO: Found %d proposals for %s\n", len(result.Proposals), repo)
		}
	}
}
