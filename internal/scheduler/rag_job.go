package scheduler

import (
	"context"
	"log"
	"time"

	"go-agent-llm-orchestrator/internal/dto"
)

// StartRAGScrubbingJob runs a background goroutine that triggers RAG scrubbing on a schedule.
func StartRAGScrubbingJob(ctx context.Context, analyzer *dto.Analyzer, interval time.Duration) {
	log.Printf("Scheduler: Starting RAG scrubbing job (interval: %v)", interval)
	
	// Initial delay to avoid heavy disk IO during startup
	time.AfterFunc(2*time.Minute, func() {
		runScrub(ctx, analyzer)
	})

	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			runScrub(ctx, analyzer)
		}
	}
}

func runScrub(ctx context.Context, analyzer *dto.Analyzer) {
	log.Println("Scheduler: Running scheduled RAG scrubbing...")
	removed, err := analyzer.ScrubAllRepos(ctx)
	if err != nil {
		log.Printf("Scheduler Error: RAG scrubbing failed: %v", err)
	} else if removed > 0 {
		log.Printf("Scheduler: RAG scrubbing completed. Removed %d orphaned chunks.", removed)
	} else {
		log.Println("Scheduler: RAG scrubbing completed. No orphaned chunks found.")
	}
}
