package main

import (
	"context"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"go-agent-llm-orchestrator/internal/api"
	"go-agent-llm-orchestrator/internal/db"
	"go-agent-llm-orchestrator/internal/dto"
	gitpkg "go-agent-llm-orchestrator/internal/git"
	"go-agent-llm-orchestrator/internal/llm"
	"go-agent-llm-orchestrator/internal/monitor"
	"go-agent-llm-orchestrator/internal/notifier"
	"go-agent-llm-orchestrator/internal/prompt"
	"go-agent-llm-orchestrator/internal/scheduler"
	"go-agent-llm-orchestrator/internal/traffic"
)

func main() {
	// Set up in-memory log buffer before anything else so all startup logs are captured.
	logBuf := api.NewLogBuffer(500)

	log.Println("Starting Jules Orchestrator...")

	// 1. Configuration
	dbPath := os.Getenv("DB_PATH")
	if dbPath == "" {
		dbPath = "./data/tasks.db"
	}

	// Log active environment variables (secrets are masked).
	log.Println("=== Environment configuration ===")
	logEnvVar("DB_PATH", dbPath, false)
	logEnvVar("JULES_API_KEY", os.Getenv("JULES_API_KEY"), true)
	logEnvVar("JULES_API_URL", os.Getenv("JULES_API_URL"), false)
	logEnvVar("LLM_LOCAL_ENDPOINT", os.Getenv("LLM_LOCAL_ENDPOINT"), false)
	logEnvVar("LLM_LOCAL_MODEL", os.Getenv("LLM_LOCAL_MODEL"), false)
	logEnvVar("LLM_REMOTE_ENDPOINT", os.Getenv("LLM_REMOTE_ENDPOINT"), false)
	logEnvVar("LLM_REMOTE_API_KEY", os.Getenv("LLM_REMOTE_API_KEY"), true)
	logEnvVar("LLM_REMOTE_MODEL", os.Getenv("LLM_REMOTE_MODEL"), false)
	logEnvVar("PROMPT_LIBRARY_CACHE_DIR", os.Getenv("PROMPT_LIBRARY_CACHE_DIR"), false)
	logEnvVar("DISTRIBUTION_CONFIG_PATH", os.Getenv("DISTRIBUTION_CONFIG_PATH"), false)
	log.Println("=================================")

	// 2. Initialize Foundation
	database, err := db.InitDB(dbPath)
	if err != nil {
		log.Fatalf("Failed to initialize database: %v", err)
	}
	defer database.Close()

	tm := traffic.NewTrafficManager(1.0, 5, database)

	// 3. Initialize Logic
	julesClient := api.NewJulesClient(database)
	if url := julesClient.EffectiveBaseURL(); url != "" {
		log.Printf("  %-30s = %s", "JULES effective URL", url)
	} else {
		log.Printf("  %-30s (not set — Jules API disabled)", "JULES effective URL")
	}
	router := llm.NewRouter(database)
	supervisor := llm.NewSupervisor(database, tm, router, julesClient)
	telegramNotifier := notifier.NewTelegramNotifier(database)
	telegramNotifier.StartPolling()

	// Prompt-library git syncer: cache dir from env or default
	cacheDir := os.Getenv("PROMPT_LIBRARY_CACHE_DIR")
	if cacheDir == "" {
		cacheDir = "./data/prompt-lib"
	}
	gitSyncer := gitpkg.NewSyncer(database, cacheDir)
	promptBuilder := prompt.NewBuilder(database, cacheDir)

	engine := scheduler.NewEngine(database, tm, julesClient, telegramNotifier, promptBuilder)
	dtoMgr := dto.NewTemplateManager(database)
	analyzer := dto.NewAnalyzer(database, router, promptBuilder)
	statMonitor := monitor.NewMonitor(database, tm, julesClient, supervisor)
	healthMonitor := monitor.NewHealthMonitor()
	healthMonitor.Start()

	adminServer := api.NewAdminServer(database, engine, dtoMgr, analyzer)
	adminServer.SetHealthMonitor(healthMonitor)
	adminServer.SetLogBuffer(logBuf)
	adminServer.SetGitSyncer(gitSyncer)
	adminServer.SetPromptChecker(promptBuilder)

	// 4. Start Background Processes
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	engine.Start()

	// When the prompt-library syncs successfully for the first time, auto-resume
	// any tasks that were paused at startup due to a missing SSH key.
	gitSyncer.OnSyncSuccess = func() {
		n := engine.ResumeAutopaused(ctx)
		if n > 0 {
			log.Printf("git: prompt-library ready — %d auto-paused task(s) resumed", n)
		}
	}

	// Start git syncer for prompt-library (runs initial sync then polls)
	go gitSyncer.Start(ctx)

	// Proactively pause all PENDING tasks if PAT is not yet configured —
	// they would fail anyway when the cron fires and buildPrompt() returns an error.
	if !gitSyncer.IsPATConfigured() {
		n := engine.PauseAllPending(ctx)
		log.Printf("WARNING: prompt-library GitHub PAT not set — %d PENDING task(s) paused. Set PAT via Settings → Prompt Library, they will resume automatically after first successful sync.", n)
	}

	// Import distribution config if available
	distPath := os.Getenv("DISTRIBUTION_CONFIG_PATH")
	if distPath != "" {
		if _, err := os.Stat(distPath); err == nil {
			log.Printf("Loading distribution config from %s", distPath)
			if err := engine.ImportDistribution(distPath); err != nil {
				log.Printf("Failed to import distribution config: %v", err)
			}
		}
	}

	// Initial task sync
	if err := engine.SyncTasks(ctx); err != nil {
		log.Printf("Failed to sync initial tasks: %v", err)
	}

	go statMonitor.Start(ctx, 30*time.Second)

	// Periodic task sync (every 5 minutes)
	go func() {
		ticker := time.NewTicker(5 * time.Minute)
		defer ticker.Stop()
		for {
			select {
			case <-ticker.C:
				if err := engine.SyncTasks(ctx); err != nil {
					log.Printf("Failed to sync tasks: %v", err)
				}
			case <-ctx.Done():
				return
			}
		}
	}()

	// Daily summary at 09:00
	go func() {
		for {
			now := time.Now()
			next := time.Date(now.Year(), now.Month(), now.Day(), 9, 0, 0, 0, now.Location())
			if now.After(next) {
				next = next.Add(24 * time.Hour)
			}
			time.Sleep(time.Until(next))
			log.Println("Sending daily summary to Telegram")
			telegramNotifier.SendDailySummary(10, 0, 2)
		}
	}()

	go func() {
		log.Println("Admin API server starting on :8080")
		if err := adminServer.Start(":8080"); err != nil {
			log.Printf("Admin API server failed: %v", err)
		}
	}()

	log.Println("Orchestrator is running and monitoring tasks")

	// 5. Graceful Shutdown
	stop := make(chan os.Signal, 1)
	signal.Notify(stop, os.Interrupt, syscall.SIGTERM)

	<-stop
	log.Println("Shutting down gracefully...")

	engine.Stop()
	cancel()

	time.Sleep(2 * time.Second)
	log.Println("Orchestrator stopped")
}

// logEnvVar logs the name and value of an environment variable.
// If secret is true, the value is masked.
func logEnvVar(name, value string, secret bool) {
	if value == "" {
		log.Printf("  %-30s (not set)", name)
		return
	}
	display := value
	if secret {
		if len(value) <= 8 {
			display = "***"
		} else {
			display = value[:4] + "..." + value[len(value)-4:]
		}
	}
	log.Printf("  %-30s = %s", name, display)
}
