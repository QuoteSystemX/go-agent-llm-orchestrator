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
	"go-agent-llm-orchestrator/internal/rag"
)

type Analyzer struct {
	db            *db.DB
	router        *llm.Router
	promptBuilder *prompt.Builder
	ragStore      *rag.MemoryStore
}

func NewAnalyzer(database *db.DB, router *llm.Router, pb *prompt.Builder) *Analyzer {
	return &Analyzer{
		db:            database,
		router:        router,
		promptBuilder: pb,
		ragStore:      rag.NewMemoryStore(),
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
	Proposals    []Proposal        `json:"proposals"`
	CurrentStage string            `json:"current_stage"` // discovery, prd, architecture, stories, sprint, worker, closure
	Progress     int               `json:"progress"`      // 0-100%
	Warnings     []string          `json:"warnings"`      // Warnings about missing data
	Metadata     map[string]string `json:"metadata"`      // Project metadata (language, etc)
}

func (a *Analyzer) AnalyzeRepo(ctx context.Context, repoName string) (*AnalysisResult, error) {
	basePath := a.db.GetSetting("repo_base_path", "./repos")
	repoPath := filepath.Join(basePath, repoName)

	if _, err := os.Stat(repoPath); os.IsNotExist(err) {
		return nil, fmt.Errorf("repository directory not found: %s", repoPath)
	}

	var warnings []string
	metadata := make(map[string]string)

	// 1. Gather repository intel
	readme, err := a.readFile(filepath.Join(repoPath, "README.md"))
	if err != nil {
		warnings = append(warnings, "README.md not found or unreadable")
	} else {
		metadata["has_readme"] = "true"
	}

	wiki, _ := a.readDir(filepath.Join(repoPath, "wiki"), ".md")
	if wiki == "" {
		warnings = append(warnings, "No wiki pages found in 'wiki/' directory")
	}
	
	// Check for .agent folder (BMAD context)
	// 3. Index and Search Context (RAG)
	a.ragStore.Reset()
	docFiles := []string{filepath.Join(repoPath, "README.md")}
	// Also index everything in .agent and wiki
	if files, err := os.ReadDir(filepath.Join(repoPath, "wiki")); err == nil {
		for _, f := range files {
			if !f.IsDir() {
				docFiles = append(docFiles, filepath.Join(repoPath, "wiki", f.Name()))
			}
		}
	}
	
	for _, f := range docFiles {
		if _, err := os.Stat(f); err == nil {
			a.indexFile(f)
		}
	}

	// Search for relevant context for "Dynamic Task Orchestration"
	docContext := a.SearchContext("task orchestration project structure goals", 5)

	// 4. Get active tasks
	agentContext := ""
	if _, err := os.Stat(filepath.Join(repoPath, ".agent")); err == nil {
		metadata["has_agent"] = "true"
		workflows, _ := a.readDir(filepath.Join(repoPath, ".agent", "workflows"), ".md")
		skills, _ := a.readDir(filepath.Join(repoPath, ".agent", "skills"), ".md")
		knowledge, _ := a.readFile(filepath.Join(repoPath, ".agent", "KNOWLEDGE.md"))
		arch, _ := a.readFile(filepath.Join(repoPath, ".agent", "ARCHITECTURE.md"))
		
		agentContext = fmt.Sprintf("### Repository .agent Context\nWorkflows:\n%s\nSkills:\n%s\nKnowledge:\n%s\nArchitecture:\n%s\nContext RAG:\n%s\n", 
			workflows, skills, knowledge, arch, docContext)
	} else {
		warnings = append(warnings, "No .agent folder found (BMAD context missing)")
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
		return nil, fmt.Errorf("LLM analysis failed: %w", err)
	}
	
	// 4. Parse response
	result, err := a.parseAnalysisResult(response)
	if err != nil {
		return nil, err
	}
	
	result.Warnings = append(result.Warnings, warnings...)
	result.Metadata = metadata
	return result, nil
}

func (a *Analyzer) readFile(path string) (string, error) {
	data, err := ioutil.ReadFile(path)
	if err != nil {
		return "", err
	}
	content := string(data)
	if len(content) > 5000 {
		content = content[:5000] + "... [truncated]"
	}
	return content, nil
}

func (a *Analyzer) readDir(path string, ext string) (string, error) {
	files, err := ioutil.ReadDir(path)
	if err != nil {
		return "", err
	}
	var content strings.Builder
	totalLen := 0
	for _, f := range files {
		if !f.IsDir() && filepath.Ext(f.Name()) == ext {
			data, _ := ioutil.ReadFile(filepath.Join(path, f.Name()))
			s := string(data)
			if totalLen+len(s) > 10000 {
				content.WriteString(fmt.Sprintf("File: %s\n%s\n... [truncated dir reading]\n", f.Name(), s[:10000-totalLen]))
				break
			}
			content.WriteString(fmt.Sprintf("File: %s\n%s\n---\n", f.Name(), s))
			totalLen += len(s)
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

func (a *Analyzer) SearchContext(query string, topK int) string {
	relevantDocs := a.ragStore.Search(query, topK)
	context := ""
	for _, d := range relevantDocs {
		context += fmt.Sprintf("--- Source: %s ---\n%s\n", d.Source, d.Content)
	}
	return context
}

func (a *Analyzer) indexFile(path string) {
	content, err := os.ReadFile(path)
	if err != nil {
		return
	}

	text := string(content)
	chunkSize := 1000
	overlap := 200
	for i := 0; i < len(text); i += (chunkSize - overlap) {
		end := i + chunkSize
		if end > len(text) {
			end = len(text)
		}
		a.ragStore.AddDocument(rag.Document{
			ID:      fmt.Sprintf("%s_%d", path, i),
			Source:  filepath.Base(path),
			Content: text[i:end],
		})
		if end == len(text) {
			break
		}
	}
}
