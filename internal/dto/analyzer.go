package dto

import (
	"context"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"os"
	"path/filepath"
	"strings"
	"time"

	"go-agent-llm-orchestrator/internal/db"
	"go-agent-llm-orchestrator/internal/git"
	"go-agent-llm-orchestrator/internal/llm"
	"go-agent-llm-orchestrator/internal/prompt"
	"go-agent-llm-orchestrator/internal/rag"
)

type Analyzer struct {
	db            *db.DB
	router        *llm.Router
	promptBuilder *prompt.Builder
	ragStore      *rag.MemoryStore
	syncer        *git.Syncer
}

func NewAnalyzer(database *db.DB, router *llm.Router, pb *prompt.Builder, syncer *git.Syncer) *Analyzer {
	return &Analyzer{
		db:            database,
		router:        router,
		promptBuilder: pb,
		ragStore:      rag.NewMemoryStore(),
		syncer:        syncer,
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
	LastAnalysis string            `json:"last_analysis"`
}

func (a *Analyzer) AnalyzeRepo(ctx context.Context, repoName string) (*AnalysisResult, error) {
	basePath := a.db.GetSetting("repo_base_path", "./data/repos")
	repoPath := filepath.Join(basePath, repoName)

	// Ensure repo is synced on PVC
	if a.syncer != nil {
		log.Printf("DTO [%s]: Syncing repository to %s...", repoName, repoPath)
		rawUrl := fmt.Sprintf("https://github.com/%s.git", repoName)
		if err := a.syncer.SyncCustom(ctx, rawUrl, "main", repoPath); err != nil {
			log.Printf("DTO [%s]: Sync failed: %v. Proceeding with existing files if any.", repoName, err)
		}
	}

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

	// Extensions to index
	targetExts := map[string]bool{
		".md": true, ".go": true, ".js": true, ".ts": true,
		".py": true, ".sql": true, ".yaml": true, ".yml": true, ".json": true,
	}

	fileCount := 0
	maxFiles := 500
	maxFileSize := int64(100 * 1024) // 100 KB

	log.Printf("DTO [%s]: Scanning repository files...", repoName)
	filepath.Walk(repoPath, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() {
			return nil
		}
		if fileCount >= maxFiles {
			return filepath.SkipDir // Stop walking once we hit the limit
		}

		// Skip common noise directories and large files
		ignoredDirs := []string{
			"/node_modules/", "/.git/", "/vendor/", "/dist/", "/build/",
			"/target/", "/bin/", "/obj/", "/.idea/", "/.vscode/",
			"/.venv/", "/__pycache__/", "/pkg/",
		}
		for _, dir := range ignoredDirs {
			if strings.Contains(path, dir) {
				return nil
			}
		}
		if info.Size() > maxFileSize {
			return nil
		}

		ext := filepath.Ext(path)
		if targetExts[ext] {
			a.indexFile(path)
			fileCount++
		}
		return nil
	})

	log.Printf("DTO [%s]: Indexed %d files. Searching for project context...", repoName, fileCount)
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

	// Get context window for truncation
	windowStr := a.db.GetSetting("llm_local_context_window", "4096")
	var window int
	fmt.Sscanf(windowStr, "%d", &window)
	if window <= 0 {
		window = 4096
	}
	maxChars := window * 3 // Conservative estimate: 3 chars per token

	// 2. Build prompt with dynamic truncation
	prompt := a.buildAnalysisPrompt(repoName, readme, wiki, agentContext, currentTasks, templates, maxChars)

	// 3. Call LLM
	log.Printf("DTO [%s]: Requesting LLM analysis (this may take a minute)...", repoName)
	response, err := a.router.GenerateResponse(ctx, llm.DTO, prompt)
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
	result.LastAnalysis = time.Now().Format(time.RFC3339)

	// Persist last analysis time
	a.db.SetSetting("dto_last_analysis_"+repoName, result.LastAnalysis)

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

func (a *Analyzer) buildAnalysisPrompt(repoName, readme, wiki, agentContext string, currentTasks []map[string]any, templates []Template, maxChars int) string {
	// 1. Define Instructions
	instructions := "Your goal: Propose 3-5 new tasks or updates. Focus on the FULL BMAD methodology cycle:\n" +
		"1. Planning: /discovery -> /prd -> /architecture -> /stories -> /sprint\n" +
		"2. Execution: Worker tasks (implementing features/fixes)\n" +
		"3. Maintenance: /sprint-closer and Wiki/Docs actualization.\n\n" +
		"Return ONLY a JSON object with fields: current_stage, progress, proposals.\n"

	// 2. Budgeting
	ctxBudget := maxChars - 2000
	if ctxBudget < 2000 { ctxBudget = 2000 }

	// Format Tasks first to see their size
	var tasksSb strings.Builder
	for _, t := range currentTasks {
		tasksSb.WriteString(fmt.Sprintf("- %v: %v (Pattern: %v)\n", t["id"], t["mission"], t["pattern"]))
	}
	tasksStr := tasksSb.String()

	// 3. Trim sections
	rOrig := len(readme)
	rLimit := ctxBudget * 20 / 100
	if len(readme) > rLimit { readme = readme[:rLimit] + "... [truncated]" }
	
	wOrig := len(wiki)
	wLimit := ctxBudget * 20 / 100
	if len(wiki) > wLimit { wiki = wiki[:wLimit] + "... [truncated]" }

	tOrig := len(tasksStr)
	tLimit := ctxBudget * 15 / 100
	if len(tasksStr) > tLimit { tasksStr = tasksStr[:tLimit] + "... [truncated]" }

	ragContext := a.SearchContext(repoName, 5)
	ragOrig := len(ragContext)
	ragLimit := ctxBudget - len(readme) - len(wiki) - len(tasksStr) - len(agentContext)
	if len(ragContext) > ragLimit && ragLimit > 0 {
		ragContext = ragContext[:ragLimit] + "... [truncated]"
	}

	log.Printf("DTO [%s] Context Budgeting:\n"+
		"  - README: %d -> %d chars\n"+
		"  - Wiki:   %d -> %d chars\n"+
		"  - Tasks:  %d -> %d chars\n"+
		"  - RAG:    %d -> %d chars\n",
		repoName, rOrig, len(readme), wOrig, len(wiki), tOrig, len(tasksStr), ragOrig, len(ragContext))

	// 4. Assemble
	var sb strings.Builder
	sb.WriteString(fmt.Sprintf("Repository Analysis: %s\n\n", repoName))
	if readme != "" { sb.WriteString("=== README ===\n" + readme + "\n\n") }
	if wiki != "" { sb.WriteString("=== Wiki ===\n" + wiki + "\n\n") }
	if tasksStr != "" { sb.WriteString("=== Tasks ===\n" + tasksStr + "\n\n") }
	if ragContext != "" { sb.WriteString("=== Code ===\n" + ragContext + "\n\n") }

	if len(templates) > 0 {
		sb.WriteString("=== Templates ===\n")
		for i, t := range templates {
			if i >= 2 { break } // Limit to 2 templates
			sb.WriteString(fmt.Sprintf("- %s: %s\n", t.Name, t.Content))
		}
		sb.WriteString("\n")
	}

	sb.WriteString("=== Instructions ===\n")
	sb.WriteString(instructions)

	finalPrompt := sb.String()
	log.Printf("DTO [%s]: Final prompt size: %d chars", repoName, len(finalPrompt))
	return finalPrompt
}

func (a *Analyzer) parseAnalysisResult(response string) (*AnalysisResult, error) {
	// Simple JSON extraction from markdown (handle both { } and [ ])
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
	runes := []rune(text)
	chunkSize := 1000
	overlap := 200
	for i := 0; i < len(runes); i += (chunkSize - overlap) {
		end := i + chunkSize
		if end > len(runes) {
			end = len(runes)
		}
		a.ragStore.AddDocument(rag.Document{
			ID:      fmt.Sprintf("%s_%d", path, i),
			Source:  filepath.Base(path),
			Content: string(runes[i:end]),
		})
		if end == len(runes) {
			break
		}
	}
}
