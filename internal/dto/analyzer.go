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
	"sync"
	"time"

	"go-agent-llm-orchestrator/internal/db"
	"go-agent-llm-orchestrator/internal/git"
	"go-agent-llm-orchestrator/internal/llm"
	"go-agent-llm-orchestrator/internal/prompt"
	"go-agent-llm-orchestrator/internal/rag"
)

type RepoAnalysisState struct {
	IsRunning    bool   `json:"is_running"`
	Type         string `json:"type"` // "MANUAL" or "BACKGROUND"
	Phase        string `json:"phase"`
	CurrentFile  string `json:"current_file"`
	FilesIndexed int    `json:"files_indexed"`
	TotalFiles   int    `json:"total_files"`
}

type Analyzer struct {
	db            *db.DB
	router        *llm.Router
	promptBuilder *prompt.Builder
	ragStores     map[string]*rag.MemoryStore
	ragMu         sync.RWMutex
	inferMu       *sync.RWMutex
	syncer        *git.Syncer

	stateMutex sync.RWMutex
	state      map[string]*RepoAnalysisState
}

func NewAnalyzer(database *db.DB, router *llm.Router, pb *prompt.Builder, syncer *git.Syncer) *Analyzer {
	return &Analyzer{
		db:            database,
		router:        router,
		promptBuilder: pb,
		ragStores:     make(map[string]*rag.MemoryStore),
		syncer:        syncer,
		state:         make(map[string]*RepoAnalysisState),
	}
}


func (a *Analyzer) getRagStore(repoID string) *rag.MemoryStore {
	a.ragMu.Lock()
	defer a.ragMu.Unlock()

	if s, ok := a.ragStores[repoID]; ok {
		return s
	}

	basePath := filepath.Join(a.db.GetSetting("repo_base_path", "./data/repos"), "../chromem_db")
	ollamaUrl := a.db.GetSetting("llm_local_endpoint", "http://localhost:11434")
	modelName := a.db.GetSetting("llm_embedding_model", "nomic-embed-text")

	s := rag.NewMemoryStore(basePath, repoID, ollamaUrl, modelName)
	if a.inferMu != nil {
		s.SetInferencePriority(a.inferMu)
	}
	a.ragStores[repoID] = s
	return s
}

func (a *Analyzer) updateState(repoName, phase, file string, indexed int, total int) {
	a.stateMutex.Lock()
	defer a.stateMutex.Unlock()
	if s, ok := a.state[repoName]; ok {
		if phase != "" { s.Phase = phase }
		if file != "" { s.CurrentFile = file }
		if indexed >= 0 { s.FilesIndexed = indexed }
		if total >= 0 { s.TotalFiles = total }
	}
}

func (a *Analyzer) GetStatus(repoName string) *RepoAnalysisState {
	a.stateMutex.RLock()
	defer a.stateMutex.RUnlock()
	if s, ok := a.state[repoName]; ok {
		return &RepoAnalysisState{
			IsRunning:    s.IsRunning,
			Type:         s.Type,
			Phase:        s.Phase,
			CurrentFile:  s.CurrentFile,
			FilesIndexed: s.FilesIndexed,
			TotalFiles:   s.TotalFiles,
		}
	}
	return &RepoAnalysisState{IsRunning: false}
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

func (a *Analyzer) AnalyzeRepo(ctx context.Context, repoName string, isBackground bool) (*AnalysisResult, error) {
	a.stateMutex.Lock()
	state, exists := a.state[repoName]
	if !exists {
		state = &RepoAnalysisState{}
		a.state[repoName] = state
	}
	if state.IsRunning {
		a.stateMutex.Unlock()
		return nil, fmt.Errorf("analysis already running for this repository (%s)", state.Type)
	}
	state.IsRunning = true
	state.Type = "MANUAL"
	if isBackground {
		state.Type = "BACKGROUND"
	}
	state.Phase = "Initializing"
	state.FilesIndexed = 0
	state.TotalFiles = 0
	state.CurrentFile = ""
	a.stateMutex.Unlock()

	defer func() {
		a.stateMutex.Lock()
		if s, ok := a.state[repoName]; ok {
			s.IsRunning = false
			s.Phase = ""
		}
		a.stateMutex.Unlock()
	}()

	basePath := a.db.GetSetting("repo_base_path", "./data/repos")
	repoPath := filepath.Join(basePath, repoName)

	// Ensure repo is synced on PVC
	if a.syncer != nil {
		a.updateState(repoName, "Syncing Repository", "", -1, -1)
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

	if _, err := os.Stat(filepath.Join(repoPath, "wiki")); os.IsNotExist(err) {
		warnings = append(warnings, "No wiki pages found in 'wiki/' directory")
	}

	// Check for .agent folder (BMAD context)
	// 3. Index and Search Context (RAG)
	// a.ragStore.Reset() is removed to allow incremental/persistent RAG

	// Extensions to index
	targetExts := map[string]bool{
		".md": true, ".go": true, ".js": true, ".ts": true,
		".py": true, ".sql": true, ".yaml": true, ".yml": true, ".json": true,
	}

	fileCount := 0
	ragStore := a.getRagStore(repoName)
	batchSizeStr := a.db.GetSetting("dto_batch_size", "500")
	maxFiles := 500
	fmt.Sscanf(batchSizeStr, "%d", &maxFiles)

	maxFileSize := int64(100 * 1024) // 100 KB

	log.Printf("DTO [%s]: Pre-scanning files...", repoName)
	totalToIndex := 0
	filepath.Walk(repoPath, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() { return nil }
		if info.Size() > maxFileSize { return nil }
		
		// Use same ignore list
		ignoredDirs := []string{"/node_modules/", "/.git/", "/vendor/", "/dist/", "/build/", "/target/", "/bin/", "/obj/", "/.idea/", "/.vscode/", "/.venv/", "/__pycache__/", "/pkg/"}
		for _, dir := range ignoredDirs {
			if strings.Contains(path, dir) { return nil }
		}

		ext := filepath.Ext(path)
		if targetExts[ext] {
			modTime := info.ModTime().Unix()
			if !ragStore.IsIndexed(path, modTime) {
				totalToIndex++
			}
		}
		return nil
	})
	a.updateState(repoName, "", "", -1, totalToIndex)

	log.Printf("DTO [%s]: Scanning repository files (%d new files to index)...", repoName, totalToIndex)
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
			modTime := info.ModTime().Unix()
			if !ragStore.IsIndexed(path, modTime) {
				a.updateState(repoName, "Indexing Files", filepath.Base(path), fileCount, -1)
				if err := a.indexFile(ctx, path, ragStore); err == nil {
					ragStore.MarkIndexed(path, modTime)
					fileCount++
					a.updateState(repoName, "", "", fileCount, -1)
					
					// Save index incrementally every 20 files to persist progress
					if fileCount % 20 == 0 {
						ragStore.SaveIndex()
					}
				} else {
					log.Printf("DTO [%s]: Skipping marking %s as indexed due to error", repoName, path)
				}
			}
		}
		return nil
	})

	ragStore.SaveIndex()
	log.Printf("DTO [%s]: Indexed %d new/modified files. Searching for project context...", repoName, fileCount)


	// 4. Get active tasks
	if _, err := os.Stat(filepath.Join(repoPath, ".agent")); err == nil {
		metadata["has_agent"] = "true"
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
	prompt := a.buildAnalysisPrompt(repoName, readme, currentTasks, templates, maxChars)

	// 3. Call LLM
	a.updateState(repoName, "Analyzing with LLM", "", -1, -1)
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

func (a *Analyzer) buildAnalysisPrompt(repoName, readme string, currentTasks []map[string]any, templates []Template, maxChars int) string {
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

	// 3. Trim sections (Phase 4: Reduce hard limits, rely on RAG)
	rOrig := len(readme)
	rLimit := 1000 // Just a brief overview
	if len(readme) > rLimit { readme = readme[:rLimit] + "... [truncated, RAG handles the rest]" }

	tOrig := len(tasksStr)
	tLimit := ctxBudget * 15 / 100
	if len(tasksStr) > tLimit { tasksStr = tasksStr[:tLimit] + "... [truncated]" }

	// Semantic query based on active tasks
	ragQuery := repoName + " overview architecture " + tasksStr
	if tasksStr == "" {
		ragQuery = repoName + " README project description rules"
	}
	ragContext := a.SearchContext(context.Background(), repoName, ragQuery, 15) // Fetch up to 15 relevant chunks
	ragOrig := len(ragContext)
	
	ragLimit := ctxBudget - len(readme) - len(tasksStr)
	if ragLimit < 0 { ragLimit = 0 }
	if len(ragContext) > ragLimit {
		if ragLimit > 15 {
			ragContext = ragContext[:ragLimit] + "... [truncated]"
		} else {
			ragContext = ""
		}
	}

	log.Printf("DTO [%s] Context Budgeting:\n"+
		"  - README: %d -> %d chars\n"+
		"  - Tasks:  %d -> %d chars\n"+
		"  - RAG:    %d -> %d chars\n",
		repoName, rOrig, len(readme), tOrig, len(tasksStr), ragOrig, len(ragContext))

	// 4. Assemble
	var sb strings.Builder
	sb.WriteString(fmt.Sprintf("Repository Analysis: %s\n\n", repoName))
	if readme != "" { sb.WriteString("=== README ===\n" + readme + "\n\n") }
	if tasksStr != "" { sb.WriteString("=== Tasks ===\n" + tasksStr + "\n\n") }
	if ragContext != "" { sb.WriteString("=== RAG Context ===\n" + ragContext + "\n\n") }

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
	startObj := strings.Index(response, "{")
	startArr := strings.Index(response, "[")

	if startArr != -1 && (startObj == -1 || startArr < startObj) {
		if end := strings.LastIndex(response, "]"); end != -1 {
			jsonStr = response[startArr : end+1]
		}
	} else if startObj != -1 {
		if end := strings.LastIndex(response, "}"); end != -1 {
			jsonStr = response[startObj : end+1]
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
		result, err := a.AnalyzeRepo(ctx, repo, true)
		if err != nil {
			fmt.Printf("DTO: Scheduled analysis failed for %s: %v\n", repo, err)
			continue
		}

		if len(result.Proposals) > 0 {
			fmt.Printf("DTO: Found %d proposals for %s\n", len(result.Proposals), repo)
		}
	}
}

// SetInferencePriority wires up the Ollama priority gate from llm.Router so
// embedding calls yield to inference requests on the shared local model.
func (a *Analyzer) SetInferencePriority(router *llm.Router) {
	a.inferMu = router.InferenceMutex()
}

func (a *Analyzer) SearchContext(ctx context.Context, repoName, query string, topK int) string {
	ragStore := a.getRagStore(repoName)
	log.Printf("DTO [%s]: Querying RAG for top %d chunks matching semantic query: '%s'", repoName, topK, query)
	relevantDocs := ragStore.Search(ctx, query, topK)
	log.Printf("DTO: RAG found %d relevant chunks for query", len(relevantDocs))
	
	context := ""
	for _, d := range relevantDocs {
		context += fmt.Sprintf("--- Source: %s ---\n%s\n", d.Source, d.Content)
	}
	return context
}

func chunkParams(ext string) (chunkSize, overlap int) {
	switch ext {
	case ".go", ".js", ".ts", ".jsx", ".tsx", ".py":
		return 300, 60
	case ".json", ".yaml", ".yml", ".sql":
		return 250, 50
	default: // .md, .txt and others
		return 700, 140
	}
}

func (a *Analyzer) indexFile(ctx context.Context, path string, store *rag.MemoryStore) error {
	content, err := os.ReadFile(path)
	if err != nil {
		return err
	}

	text := string(content)
	runes := []rune(text)
	chunkSize, overlap := chunkParams(filepath.Ext(path))

	chunksCount := len(runes) / (chunkSize - overlap)
	if chunksCount == 0 { chunksCount = 1 }
	log.Printf("DTO: Generating embeddings for %s (%d chunks)...", filepath.Base(path), chunksCount)

	startTime := time.Now()
	for i := 0; i < len(runes); i += (chunkSize - overlap) {
		end := i + chunkSize
		if end > len(runes) {
			end = len(runes)
		}
		err := store.AddDocument(ctx, rag.Document{
			ID:      fmt.Sprintf("%s_%d", path, i),
			Source:  path,
			Content: string(runes[i:end]),
		})
		if err != nil {
			return err
		}
		if end == len(runes) {
			break
		}
	}
	
	duration := time.Since(startTime)
	if duration > 1*time.Second {
		log.Printf("DTO: Embedding generation for %s took %v", filepath.Base(path), duration)
	}
	return nil
}
