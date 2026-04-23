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
	gitpkg "go-agent-llm-orchestrator/internal/git"
	"go-agent-llm-orchestrator/internal/llm"
	"go-agent-llm-orchestrator/internal/monitor"
	"go-agent-llm-orchestrator/internal/notifier"
	"go-agent-llm-orchestrator/internal/prompt"
	"go-agent-llm-orchestrator/internal/scheduler"
	"go-agent-llm-orchestrator/internal/traffic"
)

func main() {
	log.Println("Starting Jules Orchestrator...")

	// 1. Configuration
	dbPath := os.Getenv("DB_PATH")
	if dbPath == "" {
		dbPath = "./data/tasks.db"
	}

	// 2. Initialize Foundation
	database, err := db.InitDB(dbPath)
	if err != nil {
		log.Fatalf("Failed to initialize database: %v", err)
	}
	defer database.Close()

	tm := traffic.NewTrafficManager(1.0, 5) // 1 RPS, 5 burst (example)

	// 3. Initialize Logic
	julesClient := api.NewJulesClient(database)
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
	promptBuilder := prompt.NewBuilder(cacheDir)

	engine := scheduler.NewEngine(database, tm, julesClient, telegramNotifier, promptBuilder)
	statMonitor := monitor.NewMonitor(database, tm, julesClient, supervisor)
	adminServer := api.NewAdminServer(database, engine)

	// 4. Start Background Processes
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	engine.Start()

	// Start git syncer for prompt-library (runs initial sync then polls)
	go gitSyncer.Start(ctx)
	
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

	// Periodic task sync (Every 5 minutes)
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
	
	// Start Daily Summary (Every day at 09:00)
	go func() {
		for {
			now := time.Now()
			next := time.Date(now.Year(), now.Month(), now.Day(), 9, 0, 0, 0, now.Location())
			if now.After(next) {
				next = next.Add(24 * time.Hour)
			}
			time.Sleep(time.Until(next))
			log.Println("Sending daily summary to Telegram")
			telegramNotifier.SendDailySummary(10, 0, 2) // Example counts for now
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
	
	// Give some time for background tasks to finish
	time.Sleep(2 * time.Second)
	log.Println("Orchestrator stopped")
}
