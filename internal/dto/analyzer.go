package dto

import (
	"context"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"os"
	"os/exec"
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
	IsRunning      bool            `json:"is_running"`
	Type           string          `json:"type"` // "MANUAL" or "BACKGROUND"
	Phase          string          `json:"phase"`
	CurrentFile    string          `json:"current_file"`
	FilesIndexed   int             `json:"files_indexed"`
	AlreadyIndexed int             `json:"already_indexed"`
	TotalFiles     int             `json:"total_files"`
	Proposals      *AnalysisResult `json:"proposals,omitempty"`
	Error          string          `json:"error,omitempty"`
}

type Analyzer struct {
	db            *db.DB
	router        *llm.Router
	promptBuilder *prompt.Builder
	ragManager    *rag.Manager
	inferMu       *sync.RWMutex
	syncer        *git.Syncer

	stateMutex sync.RWMutex
	state      map[string]*RepoAnalysisState

	appCtx context.Context
	sem    chan struct{}

	onUpdate func(repoURL string, state *RepoAnalysisState)

	sessionMgr *SessionManager
	pusher     *git.Pusher
}

func NewAnalyzer(appCtx context.Context, database *db.DB, router *llm.Router, pb *prompt.Builder, syncer *git.Syncer) *Analyzer {
	dbDir := filepath.Dir(database.GetSetting("repo_base_path", "./data/repos"))
	sm, err := NewSessionManager(dbDir)
	if err != nil {
		log.Printf("Analyzer: Failed to initialize SessionManager: %v", err)
	}

	return &Analyzer{
		db:            database,
		router:        router,
		promptBuilder: pb,
		ragManager:    rag.NewManager(),
		syncer:        syncer,
		state:         make(map[string]*RepoAnalysisState),
		appCtx:        appCtx,
		sem:           make(chan struct{}, 1), // Only 1 manual analysis at a time
		sessionMgr:    sm,
		pusher:        git.NewPusher(database, filepath.Dir(database.GetSetting("repo_base_path", "./data/repos"))),
	}
}


func (a *Analyzer) getRagStore(repoID string) *rag.MemoryStore {
	if s := a.ragManager.GetStore(repoID); s != nil {
		return s
	}

	basePath := filepath.Join(a.db.GetSetting("repo_base_path", "./data/repos"), "../chromem_db")
	ollamaUrl := a.db.GetSetting("llm_local_endpoint", "http://localhost:11434")
	modelName := a.db.GetSetting("llm_embedding_model", "nomic-embed-text")

	s := rag.NewMemoryStore(basePath, repoID, ollamaUrl, modelName)
	if a.inferMu != nil {
		s.SetInferencePriority(a.inferMu)
	}
	a.ragManager.RegisterStore(repoID, s)
	return s
}

// DiscoverExistingStores scans the database for repositories and initializes
// their RAG stores if they already exist on disk. This ensures they are visible
// in the UI immediately after server restart.
func (a *Analyzer) DiscoverExistingStores(ctx context.Context) {
	repos, err := a.db.GetDistinctRepos(ctx)
	if err != nil {
		log.Printf("Analyzer: Failed to get repos for RAG discovery: %v", err)
		return
	}

	basePath := filepath.Join(a.db.GetSetting("repo_base_path", "./data/repos"), "../chromem_db")
	
	for _, repoID := range repos {
		// Use the same sanitization as NewMemoryStore
		safeID := rag.SanitizeID(repoID)
		dbPath := filepath.Join(basePath, safeID)
		
		// If the directory exists, it likely has an index.
		// We use getRagStore to initialize and register it.
		if _, err := os.Stat(dbPath); err == nil {
			log.Printf("Analyzer: Auto-discovered existing RAG index for %s", repoID)
			a.getRagStore(repoID)
		}
	}
}

func (a *Analyzer) RecoverRepo(ctx context.Context, repoID string) error {
	store := a.getRagStore(repoID)
	if store == nil {
		return fmt.Errorf("failed to initialize RAG store for %s", repoID)
	}
	
	if err := store.Recover(ctx); err != nil {
		return err
	}

	// Trigger background analysis to repopulate the RAG store
	go func() {
		log.Printf("Analyzer: Triggering background re-analysis for %s after recovery", repoID)
		_, err := a.AnalyzeRepo(context.Background(), repoID, true)
		if err != nil {
			log.Printf("Analyzer: Background re-analysis failed for %s: %v", repoID, err)
		}
	}()

	return nil
}

func (a *Analyzer) updateState(repoName, phase, file string, indexed int, total int) {
	a.stateMutex.Lock()
	defer a.stateMutex.Unlock()
	if s, ok := a.state[repoName]; ok {
		if phase != "" { s.Phase = phase }
		if file != "" { s.CurrentFile = file }
		if indexed >= 0 { s.FilesIndexed = indexed }
		if total >= 0 { s.TotalFiles = total }
		if a.onUpdate != nil {
			a.onUpdate(repoName, s)
		}
	}
}

func (a *Analyzer) SetNotifyFunc(fn func(repoURL string, state *RepoAnalysisState)) {
	a.stateMutex.Lock()
	defer a.stateMutex.Unlock()
	a.onUpdate = fn
}

func (a *Analyzer) GetStatus(repoName string) *RepoAnalysisState {
	a.stateMutex.RLock()
	defer a.stateMutex.RUnlock()
	if s, ok := a.state[repoName]; ok {
		return &RepoAnalysisState{
			IsRunning:      s.IsRunning,
			Type:           s.Type,
			Phase:          s.Phase,
			CurrentFile:    s.CurrentFile,
			FilesIndexed:   s.FilesIndexed,
			AlreadyIndexed: s.AlreadyIndexed,
			TotalFiles:     s.TotalFiles,
			Proposals:      s.Proposals,
			Error:          s.Error,
		}
	}
	return &RepoAnalysisState{IsRunning: false}
}

// TriggerManualAnalysis starts a background repository analysis.
// It uses the application context for cancellation but detaches from the request context.
func (a *Analyzer) TriggerManualAnalysis(requestCtx context.Context, repoName string) {
	a.stateMutex.Lock()
	state, exists := a.state[repoName]
	if !exists {
		state = &RepoAnalysisState{}
		a.state[repoName] = state
	}
	if state.IsRunning {
		a.stateMutex.Unlock()
		return
	}
	a.stateMutex.Unlock()

	// Use context.WithoutCancel to preserve values (tracing, etc) but ignore request disconnects.
	// However, we also wrap it with a cancellation that listens to appCtx.
	detachedCtx := context.WithoutCancel(requestCtx)
	
	go func() {
		// Respect the global concurrency limit for manual analysis
		select {
		case a.sem <- struct{}{}:
			defer func() { <-a.sem }()
		case <-a.appCtx.Done():
			return
		}

		// Double check if app is shutting down
		if a.appCtx.Err() != nil {
			return
		}

		// We use a context that combines the detached request context with the app lifecycle.
		// Since Go doesn't have a built-in "merge" context that cancels when EITHER parent cancels,
		// we manually monitor appCtx.
		workCtx, cancel := context.WithCancel(detachedCtx)
		defer cancel()

		go func() {
			select {
			case <-a.appCtx.Done():
				cancel()
			case <-workCtx.Done():
			}
		}()

		proposals, err := a.AnalyzeRepo(workCtx, repoName, false)
		
		a.stateMutex.Lock()
		defer a.stateMutex.Unlock()
		if s, ok := a.state[repoName]; ok {
			if err != nil {
				s.Error = err.Error()
				log.Printf("DTO Error: Background manual analysis failed for %s: %v", repoName, err)
			} else {
				s.Error = ""
				s.Proposals = proposals
				log.Printf("DTO Success: Background manual analysis finished for %s", repoName)
			}
		}
	}()
}

// GetSessionManager returns the underlying session manager for interactive dialogues.
func (a *Analyzer) GetSessionManager() *SessionManager {
	return a.sessionMgr
}

// GenerateDialogueResponse uses the LLM router to generate a response for an interactive session.
func (a *Analyzer) GenerateDialogueResponse(ctx context.Context, classification llm.Classification, messages []map[string]string) (string, error) {
	// If it's a DTO classification, it will default to local. 
	// If it's Complex, it might go to remote depending on configuration.
	return a.router.GenerateChat(ctx, classification, messages, "")
}

// FinalizeStage generates an artifact based on the dialogue session and pushes it to git.
func (a *Analyzer) FinalizeStage(ctx context.Context, repoName string, stage string) error {
	if a.sessionMgr == nil {
		return fmt.Errorf("session manager not initialized")
	}

	session, err := a.sessionMgr.GetSession(ctx, repoName)
	if err != nil {
		return fmt.Errorf("failed to get session: %w", err)
	}

	// 1. Generate Artifact Content
	var artifactName, artifactContent string
	switch strings.ToLower(stage) {
	case "discovery":
		artifactName = "BRIEF.md"
		artifactContent = a.generateBriefFromSession(session)
	case "prd":
		artifactName = "PRD.md"
		artifactContent = a.generatePRDFromSession(session)
	case "architecture":
		artifactName = "ARCHITECTURE.md"
		artifactContent = a.generateArchFromSession(session)
	case "testing":
		artifactName = "TEST_REPORT.md"
		artifactContent = a.generateTestReportFromSession(session)
	case "regression":
		artifactName = "REGRESSION_REPORT.md"
		artifactContent = a.generateRegressionReportFromSession(session)
	case "docs_update":
		artifactName = "CHANGELOG.md"
		artifactContent = a.generateChangelogFromSession(session)
	default:
		return fmt.Errorf("unsupported stage for finalization: %s", stage)
	}

	// 2. Save to local repository
	repoBasePath := a.db.GetSetting("repo_base_path", "./data/repos")
	repoPath := filepath.Join(repoBasePath, repoName)
	wikiDir := filepath.Join(repoPath, "wiki")
	if err := os.MkdirAll(wikiDir, 0755); err != nil {
		return fmt.Errorf("failed to create wiki directory: %w", err)
	}

	artifactPath := filepath.Join(wikiDir, artifactName)
	if err := os.WriteFile(artifactPath, []byte(artifactContent), 0644); err != nil {
		return fmt.Errorf("failed to write artifact file: %w", err)
	}

	// 2.5 Validate Artifact (Tester Agent Role)
	if err := a.validateArtifact(ctx, artifactName, artifactContent); err != nil {
		return fmt.Errorf("artifact validation failed: %w", err)
	}

	// 3. Git Commit & Push
	branch := "main" // TODO: Detect default branch or use setting
	commitMsg := fmt.Sprintf("docs: finalize %s stage for BMAD", stage)
	relativeFilePath := filepath.Join("wiki", artifactName)
	
	if err := a.pusher.CommitAndPush(ctx, repoPath, branch, []string{relativeFilePath}, commitMsg); err != nil {
		return fmt.Errorf("git push failed: %w", err)
	}

	// 4. Update session status
	session.Status = "IDLE"
	session.CurrentStage = a.getNextStage(stage)
	a.sessionMgr.SaveSession(ctx, session)

	log.Printf("DTO: Finalized %s for %s and pushed to git", stage, repoName)
	return nil
}

func (a *Analyzer) validateArtifact(ctx context.Context, name string, content string) error {
	// In a real scenario, this would call an LLM (test-engineer) to audit the doc.
	// For now, we'll do basic structural checks.
	if len(content) < 100 {
		return fmt.Errorf("artifact %s is too short (possible generation failure)", name)
	}
	if !strings.HasPrefix(content, "# ") {
		return fmt.Errorf("artifact %s must start with an H1 header", name)
	}
	
	log.Printf("DTO: Artifact %s validated successfully", name)
	return nil
}

func (a *Analyzer) getNextStage(current string) string {
	switch strings.ToLower(current) {
	case "discovery":
		return "prd"
	case "prd":
		return "architecture"
	case "architecture":
		return "stories"
	case "stories":
		return "sprint"
	case "sprint":
		return "worker"
	case "worker":
		return "testing"
	case "testing":
		return "regression"
	case "regression":
		return "docs_update"
	case "docs_update":
		return "closure"
	default:
		return current
	}
}

func (a *Analyzer) generateBriefFromSession(s *DialogueSession) string {
	var sb strings.Builder
	sb.WriteString("# Project Brief: " + s.RepoName + "\n\n")
	sb.WriteString("## Discovery Dialogue Summary\n\n")
	for _, m := range s.Context {
		if m.Role == "system" {
			continue
		}
		role := "User"
		if m.Role == "assistant" {
			role = "Agent"
		}
		sb.WriteString(fmt.Sprintf("**%s**: %s\n\n", role, m.Content))
	}
	sb.WriteString("\n---\n*Generated by Jules DTO Orchestrator*\n")
	return sb.String()
}

func (a *Analyzer) generatePRDFromSession(s *DialogueSession) string {
	// Simple implementation for now
	return "# Product Requirements Document\n\n" + a.generateBriefFromSession(s)
}

func (a *Analyzer) generateArchFromSession(s *DialogueSession) string {
	// Simple implementation for now
	return "# System Architecture\n\n" + a.generateBriefFromSession(s)
}

func (a *Analyzer) generateTestReportFromSession(s *DialogueSession) string {
	return "# Test Report\n\n" + a.generateBriefFromSession(s)
}

func (a *Analyzer) generateRegressionReportFromSession(s *DialogueSession) string {
	return "# Regression Report\n\n" + a.generateBriefFromSession(s)
}

func (a *Analyzer) generateChangelogFromSession(s *DialogueSession) string {
	return "# Changelog\n\n" + a.generateBriefFromSession(s)
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

type FlexibleProgress int

func (p *FlexibleProgress) UnmarshalJSON(data []byte) error {
	// Try int first
	var n int
	if err := json.Unmarshal(data, &n); err == nil {
		*p = FlexibleProgress(n)
		return nil
	}
	// Try object { "steps_completed": X, "total_steps": Y }
	var obj struct {
		Completed int `json:"steps_completed"`
		Total     int `json:"total_steps"`
		Progress  int `json:"progress"`
	}
	if err := json.Unmarshal(data, &obj); err == nil {
		if obj.Total > 0 {
			*p = FlexibleProgress((obj.Completed * 100) / obj.Total)
		} else if obj.Progress > 0 {
			*p = FlexibleProgress(obj.Progress)
		}
		return nil
	}
	// Default to 0 instead of failing
	*p = 0
	return nil
}

type AnalysisResult struct {
	Proposals    []Proposal       `json:"proposals"`
	CurrentStage string           `json:"current_stage"` // discovery, prd, architecture, stories, sprint, worker, closure
	Progress     FlexibleProgress `json:"progress"`      // 0-100%
	Warnings     []string         `json:"warnings"`      // Warnings about missing data
	Metadata     map[string]string `json:"metadata"`      // Project metadata (language, etc)
	LastAnalysis string           `json:"last_analysis"`
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
	state.AlreadyIndexed = 0
	state.TotalFiles = 0
	state.CurrentFile = ""
	
	if a.onUpdate != nil {
		a.onUpdate(repoName, state)
	}
	a.stateMutex.Unlock()

	defer func() {
		a.stateMutex.Lock()
		if s, ok := a.state[repoName]; ok {
			s.IsRunning = false
			s.Phase = ""
			if a.onUpdate != nil {
				a.onUpdate(repoName, s)
			}
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

	// S4: skip the LLM call for background runs when nothing changed since the last
	// successful analysis. The check intentionally happens AFTER sync so that freshly
	// pulled commits are included in the comparison.
	if isBackground {
		if head := gitHead(repoPath); head != "" && head == a.db.GetSetting("dto_last_commit_"+repoName, "") {
			log.Printf("DTO [%s]: repo unchanged since last analysis (%s), skipping LLM call", repoName, head[:8])
			// Return cached proposals so callers can still display stage/progress.
			a.stateMutex.RLock()
			cached := a.state[repoName]
			a.stateMutex.RUnlock()
			if cached != nil && cached.Proposals != nil {
				return cached.Proposals, nil
			}
			return &AnalysisResult{LastAnalysis: a.db.GetSetting("dto_last_analysis_"+repoName, "")}, nil
		}
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

	// Capture how many files are already in the persistent index before this run.
	alreadyIndexed := ragStore.IndexedCount()
	a.stateMutex.Lock()
	if s, ok := a.state[repoName]; ok {
		s.AlreadyIndexed = alreadyIndexed
	}
	a.stateMutex.Unlock()

	log.Printf("DTO [%s]: Pre-scanning files...", repoName)
	totalToIndex := 0
	totalAllFiles := 0
	filepath.Walk(repoPath, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() { return nil }
		if info.Size() > maxFileSize { return nil }

		// Use same ignore list
		ignoredDirs := []string{"/node_modules/", "/.git/", "/vendor/", "/dist/", "/build/", "/target/", "/bin/", "/obj/", "/.idea/", "/.vscode/", "/.venv/", "/__pycache__/", "/pkg/", "/.agent/", "/.claude/"}
		for _, dir := range ignoredDirs {
			if strings.Contains(path, dir) { return nil }
		}

		ext := filepath.Ext(path)
		if targetExts[ext] {
			totalAllFiles++
			modTime := info.ModTime().Unix()
			if !ragStore.IsIndexed(path, modTime) {
				totalToIndex++
			}
		}
		return nil
	})
	a.updateState(repoName, "", "", -1, totalAllFiles)
	ragStore.SetTotalFiles(totalAllFiles)

	log.Printf("DTO [%s]: Scanning repository files (%d new files to index, %d total, %d already indexed)...", repoName, totalToIndex, totalAllFiles, alreadyIndexed)
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
			"/.venv/", "/__pycache__/", "/pkg/", "/.agent/", "/.claude/",
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
				category := categorizePath(repoPath, path)
				a.updateState(repoName, "Indexing Files", filepath.Base(path), fileCount, -1)
				// Remove stale chunks before reindexing so modified files don't
				// leave orphaned chunks from the previous (longer) version.
				if err := ragStore.RemoveDocumentsBySource(ctx, path); err != nil {
					log.Printf("DTO [%s]: FAILED to remove stale chunks for %s: %v. Skipping reindexing to avoid duplicates.", repoName, path, err)
					return nil
				}
				if err := a.indexFile(ctx, path, ragStore, category); err == nil {
					ragStore.MarkIndexed(path, modTime)
					fileCount++
					a.updateState(repoName, "", "", fileCount, -1)

					// Save index incrementally every 20 files to persist progress
					if fileCount%20 == 0 {
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

	// Determine prompt budget from Ollama /api/show so it tracks the actual model.
	// dto_prompt_budget_tokens in DB allows an explicit override (useful when Ollama
	// is unreachable or the operator wants a smaller budget for faster analysis).
	window := a.router.GetModelContextWindow()
	if override := a.db.GetSetting("dto_prompt_budget_tokens", ""); override != "" {
		var ov int
		if fmt.Sscanf(override, "%d", &ov); ov > 0 {
			window = ov
		}
	}
	if window <= 0 {
		window = 4096
	}
	// Budgeting: leave 1024 tokens for the response.
	// 2.5 chars/token is conservative for mixed code+prose.
	maxChars := int(float64(window-1024) * 2.5)
	if maxChars < 3000 {
		maxChars = 3000
	}
	
	prompt := a.buildAnalysisPrompt(ctx, repoName, readme, currentTasks, templates, maxChars)

	// 3. Call LLM
	a.stateMutex.Lock()
	if s, ok := a.state[repoName]; ok {
		s.Phase = "Analyzing with LLM"
		s.CurrentFile = ""
	}
	a.stateMutex.Unlock()
	log.Printf("DTO [%s]: Requesting LLM analysis (prompt=%d chars, ~%.0f tokens)...", repoName, len(prompt), float64(len(prompt))/2.5)
	llmStart := time.Now()
	response, err := a.router.GenerateResponse(ctx, llm.DTO, prompt)
	llmElapsed := time.Since(llmStart)
	if err != nil {
		log.Printf("DTO [%s]: LLM analysis FAILED after %v: %v", repoName, llmElapsed, err)
		return nil, fmt.Errorf("LLM analysis failed: %w", err)
	}
	log.Printf("DTO [%s]: LLM analysis completed in %v (%d chars response)", repoName, llmElapsed, len(response))

	// 4. Parse response
	result, err := a.parseAnalysisResult(response)
	if err != nil {
		return nil, err
	}

	result.Warnings = append(result.Warnings, warnings...)
	result.Metadata = metadata
	result.LastAnalysis = time.Now().Format(time.RFC3339)

	// Persist last analysis time and commit hash so the next scheduled run can
	// skip the repo if nothing has changed since this successful analysis.
	a.db.SetSetting("dto_last_analysis_"+repoName, result.LastAnalysis)
	if head := gitHead(repoPath); head != "" {
		a.db.SetSetting("dto_last_commit_"+repoName, head)
	}

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

func (a *Analyzer) buildAnalysisPrompt(ctx context.Context, repoName, readme string, currentTasks []map[string]any, templates []Template, maxChars int) string {
	// 1. Define Instructions
	instructions := "Your goal: Propose 3-5 new IMPLEMENTATION or MAINTENANCE tasks. DO NOT propose planning tasks (/discovery, /prd, /architecture, /stories, /sprint) as they are handled interactively in the chat.\n" +
		"Focus on:\n" +
		"1. Implementation: Worker tasks using patterns like featureforge, bugfix, or refactor.\n" +
		"2. Quality: Testing and regression tasks.\n" +
		"3. Maintenance: Documentation updates and /sprint-closer.\n\n" +
		"Return ONLY a JSON object with this EXACT schema:\n" +
		"{\n" +
		"  \"current_stage\": \"string (discovery|prd|architecture|stories|sprint|worker|testing|regression|docs_update|closure)\",\n" +
		"  \"progress\": \"integer (0-100)\",\n" +
		"  \"proposals\": [\n" +
		"    {\n" +
		"      \"pattern\": \"string (name of the implementation workflow, e.g. featureforge)\",\n" +
		"      \"agent\": \"string (e.g. backend-specialist)\",\n" +
		"      \"mission\": \"string (detailed task description)\",\n" +
		"      \"schedule\": \"string (CRON or @once)\",\n" +
		"      \"importance\": \"integer (1-10)\",\n" +
		"      \"category\": \"string (code|docs|test|infra)\",\n" +
		"      \"reason\": \"string (why this specific implementation is needed)\"\n" +
		"    }\n" +
		"  ]\n" +
		"}\n"

	// 2. Fixed content overhead
	header := fmt.Sprintf("Repository Analysis: %s\n\n", repoName)
	overhead := len(header) + len(instructions) + 500 // Extra 500 for section headers

	// 3. Templates budget (max 2 templates, max 1000 chars each)
	var tplSb strings.Builder
	if len(templates) > 0 {
		tplSb.WriteString("=== Templates ===\n")
		for i, t := range templates {
			if i >= 2 { break }
			content := t.Content
			if len(content) > 1000 { content = content[:1000] + "... [truncated template]" }
			tplSb.WriteString(fmt.Sprintf("- %s: %s\n", t.Name, content))
		}
		tplSb.WriteString("\n")
	}
	templateStr := tplSb.String()

	// 4. Budgeting variable parts
	variableBudget := maxChars - overhead - len(templateStr)
	if variableBudget < 1500 { variableBudget = 1500 }

	// README: 15% of variable budget
	rLimit := variableBudget * 15 / 100
	rOrig := len(readme)
	if len(readme) > rLimit {
		readme = readme[:rLimit] + "... [truncated readme]"
	}

	// Tasks: 20% of variable budget
	var tasksSb strings.Builder
	for _, t := range currentTasks {
		tasksSb.WriteString(fmt.Sprintf("- %v: %v (Pattern: %v)\n", t["id"], t["mission"], t["pattern"]))
	}
	tasksStr := tasksSb.String()
	tOrig := len(tasksStr)
	tLimit := variableBudget * 20 / 100
	if len(tasksStr) > tLimit {
		tasksStr = tasksStr[:tLimit] + "... [truncated tasks]"
	}

	// 5. RAG Context: two-phase search — meta first (wiki/tasks/README/.agent),
	// then code files for the remainder. Meta files are the highest-signal source
	// for BMAD stage detection and task proposals.
	ragLimit := variableBudget - len(readme) - len(tasksStr)
	if ragLimit < 500 {
		ragLimit = 500
	}
	metaLimit := ragLimit * 70 / 100
	codeLimit := ragLimit - metaLimit

	ragQuery := repoName + " overview architecture " + tasksStr
	if tasksStr == "" {
		ragQuery = repoName + " README project description rules"
	}

	metaContext := a.SearchContextFiltered(ctx, repoName, ragQuery, 7, "meta")
	if len(metaContext) > metaLimit {
		metaContext = metaContext[:metaLimit] + "... [truncated meta RAG]"
	}
	codeContext := a.SearchContextFiltered(ctx, repoName, ragQuery, 3, "code")
	if len(codeContext) > codeLimit {
		codeContext = codeContext[:codeLimit] + "... [truncated code RAG]"
	}
	ragContext := metaContext + codeContext
	ragOrig := len(metaContext) + len(codeContext)

	log.Printf("DTO [%s] Context Budgeting (maxChars=%d):\n"+
		"  - Header/Instr: %d chars\n"+
		"  - Templates:    %d chars\n"+
		"  - README:       %d -> %d chars\n"+
		"  - Tasks:        %d -> %d chars\n"+
		"  - RAG meta:     -> %d chars (budget %d)\n"+
		"  - RAG code:     -> %d chars (budget %d)\n"+
		"  - RAG total:    %d -> %d chars\n",
		repoName, maxChars, overhead, len(templateStr),
		rOrig, len(readme), tOrig, len(tasksStr),
		len(metaContext), metaLimit,
		len(codeContext), codeLimit,
		ragOrig, len(ragContext))

	// 6. Assemble
	var sb strings.Builder
	sb.WriteString(header)
	if readme != "" { sb.WriteString("=== README ===\n" + readme + "\n\n") }
	if tasksStr != "" { sb.WriteString("=== Tasks ===\n" + tasksStr + "\n\n") }
	if templateStr != "" { sb.WriteString(templateStr) }
	if ragContext != "" { sb.WriteString("=== RAG Context ===\n" + ragContext + "\n\n") }
	sb.WriteString("=== Instructions ===\n")
	sb.WriteString(instructions)

	finalPrompt := sb.String()
	log.Printf("DTO [%s]: Final prompt size: %d chars (estimated %.0f tokens)", 
		repoName, len(finalPrompt), float64(len(finalPrompt))/2.5)
	
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

		a.stateMutex.Lock()
		s, ok := a.state[repo]
		if !ok {
			s = &RepoAnalysisState{}
			a.state[repo] = s
		}
		// Only overwrite proposals when the LLM actually returned new ones.
		// The "unchanged commit" fast-path returns an empty Proposals slice.
		if len(result.Proposals) > 0 {
			s.Proposals = result
			fmt.Printf("DTO: Found %d proposals for %s\n", len(result.Proposals), repo)
		}
		a.stateMutex.Unlock()
	}
}

// SetInferencePriority wires up the Ollama priority gate from llm.Router so
// embedding calls yield to inference requests on the shared local model.
func (a *Analyzer) SetInferencePriority(router *llm.Router) {
	a.inferMu = router.InferenceMutex()
}

// GetModelContextWindow returns the effective context window for the current local
// model as detected from Ollama /api/show.
func (a *Analyzer) GetModelContextWindow() int {
	return a.router.GetModelContextWindow()
}

// InvalidateModelContextCache clears the cached model context window so the next
// analysis re-queries Ollama. Call this whenever the local model setting changes.
func (a *Analyzer) InvalidateModelContextCache() {
	a.router.InvalidateModelContextCache()
}

// GetRagManager returns the underlying RAG manager.
func (a *Analyzer) GetRagManager() *rag.Manager {
	return a.ragManager
}

// ScrubAllRepos triggers background cleanup for all pro-actively indexed repos.
func (a *Analyzer) ScrubAllRepos(ctx context.Context) (int, error) {
	log.Println("DTO: Starting global RAG scrubbing cycle...")
	return a.ragManager.ScrubAll(ctx)
}

func (a *Analyzer) VerifyAllRepos(ctx context.Context) map[string]error {
	if a.ragManager == nil {
		return nil
	}
	return a.ragManager.VerifyAll(ctx)
}

type SearchResult struct {
	Content string
	Sources []string
}

func (a *Analyzer) SearchContext(ctx context.Context, repoName, query string, topK int) string {
	res := a.SearchContextFull(ctx, repoName, query, topK, "")
	return res.Content
}

// SearchContextFull queries the RAG store and returns both content and sources.
func (a *Analyzer) SearchContextFull(ctx context.Context, repoName, query string, topK int, category string) SearchResult {
	ragStore := a.getRagStore(repoName)
	log.Printf("DTO [%s]: Querying RAG (category=%q) for top %d chunks: '%s'", repoName, category, topK, query)
	docs := ragStore.SearchFiltered(ctx, query, topK, category)
	log.Printf("DTO [%s]: RAG found %d chunks (category=%q)", repoName, len(docs), category)

	var sb strings.Builder
	var sources []string
	seen := make(map[string]bool)

	for _, d := range docs {
		sb.WriteString(fmt.Sprintf("--- Source: %s ---\n%s\n", d.Source, d.Content))
		if !seen[d.Source] {
			sources = append(sources, d.Source)
			seen[d.Source] = true
		}
	}
	return SearchResult{
		Content: sb.String(),
		Sources: sources,
	}
}

// SearchContextFiltered queries the RAG store filtered by category ("meta", "code", or "" for all).
func (a *Analyzer) SearchContextFiltered(ctx context.Context, repoName, query string, topK int, category string) string {
	res := a.SearchContextFull(ctx, repoName, query, topK, category)
	return res.Content
}

// categorizePath classifies a repository file as "meta" or "code".
// "meta" covers wiki, tasks, README, .agent and similar high-signal BMAD files.
// "code" covers all other source files.
func categorizePath(repoPath, filePath string) string {
	rel, err := filepath.Rel(repoPath, filePath)
	if err != nil {
		return "code"
	}
	rel = filepath.ToSlash(rel)
	switch {
	case strings.HasPrefix(rel, "wiki/"),
		strings.HasPrefix(rel, "tasks/"),
		strings.HasPrefix(rel, ".agent/"),
		rel == "README.md",
		rel == "CLAUDE.md",
		rel == "GEMINI.md":
		return "meta"
	default:
		return "code"
	}
}

// gitHead returns the current HEAD commit hash of a git repository directory,
// or an empty string when the directory is not a git repo or git is unavailable.
func gitHead(dir string) string {
	out, err := exec.Command("git", "-C", dir, "rev-parse", "HEAD").Output()
	if err != nil {
		return ""
	}
	return strings.TrimSpace(string(out))
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

func (a *Analyzer) indexFile(ctx context.Context, path string, store *rag.MemoryStore, category string) error {
	content, err := os.ReadFile(path)
	if err != nil {
		return err
	}

	text := string(content)
	runes := []rune(text)
	chunkSize, overlap := chunkParams(filepath.Ext(path))

	chunksCount := len(runes) / (chunkSize - overlap)
	if chunksCount == 0 {
		chunksCount = 1
	}
	log.Printf("DTO [%s]: Generating embeddings for %s (%d chunks, category=%s)...", store.RepoID(), filepath.Base(path), chunksCount, category)

	startTime := time.Now()
	for i := 0; i < len(runes); i += (chunkSize - overlap) {
		end := i + chunkSize
		if end > len(runes) {
			end = len(runes)
		}
		err := store.AddDocument(ctx, rag.Document{
			ID:       fmt.Sprintf("%s_%d", path, i),
			Source:   path,
			Content:  string(runes[i:end]),
			Category: category,
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
		log.Printf("DTO [%s]: Embedding generation for %s took %v", store.RepoID(), filepath.Base(path), duration)
	}
	return nil
}
