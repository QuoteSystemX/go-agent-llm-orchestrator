package main

import (
	"context"
	"flag"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"syscall"
	"time"

	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"
)

const serverVersion = "1.7.0"

func loggingMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprintf(os.Stderr, "[HTTP] %s %s %s\n", r.Method, r.URL.Path, r.URL.RawQuery)
		next.ServeHTTP(w, r)
	})
}

type handler struct {
	projectRoot string
	db          *DB
	dispatcher  *Dispatcher
	indexer     *Indexer
}

func main() {
	mode := flag.String("mode", "stdio", "transport mode: stdio|http")
	port := flag.String("port", "3200", "http listen port (mode=http only)")
	retentionDays := flag.Int("retention", 30, "Data retention in days (0 to use DB setting, default 30)")
	indexDirs := flag.String("index-dirs", ".agent,wiki,tasks", "Comma-separated directories to index for FTS5")
	root := flag.String("root", "", "project root path (overrides auto-detection)")
	dbFile := flag.String("db", "", "database file path (optional)")
	flag.Parse()

	projectRoot := *root
	if projectRoot == "" {
		if envRoot := os.Getenv("PROJECT_ROOT"); envRoot != "" {
			projectRoot = envRoot
		} else {
			projectRoot = resolveProjectRoot()
		}
	}
	fmt.Fprintf(os.Stderr, "agent-kit: version %s, projectRoot: %q\n", serverVersion, projectRoot)

	dbPath := *dbFile
	if dbPath == "" {
		dbPath = filepath.Join(projectRoot, ".agent", "mcp_server.db")
	}
	db, err := InitDB(dbPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "failed to init db: %v\n", err)
		os.Exit(1)
	}

	// Indexer initialization
	if *indexDirs != "" {
		db.SetSetting("index_dirs", *indexDirs)
	}
	activeDirs := strings.Split(db.GetSetting("index_dirs", ".agent,wiki,tasks"), ",")
	dispatcher := NewDispatcher(db, 4) // 4 concurrent workers
	idx, _ := NewIndexer(db, projectRoot, activeDirs, dispatcher)
	h := &handler{
		projectRoot: projectRoot,
		db:          db,
		dispatcher:  dispatcher,
		indexer:     idx,
	}
	h.dispatcher.Start()
	h.indexer.Start()
	
	// Data Retention initialization
	if *retentionDays > 0 {
		h.db.SetSetting("retention_days", fmt.Sprintf("%d", *retentionDays))
	}
	go h.retentionLoop()

	// Ensure essential tables are populated
	_ = h.db.SaveProposal(&CouncilProposal{
		ID:        "PROP-001",
		Title:     "Migration to Highload V2 for TON Emulator",
		Proposer:  "orchestrator",
		Votes:     2,
		Required:  3,
		Status:    "open",
		CreatedAt: time.Now(),
	})

	s := server.NewMCPServer("agent-kit", serverVersion)

	// Helper to wrap handlers with RBAC and Telemetry
	withRBAC := func(toolName string, hdlr func(context.Context, mcp.CallToolRequest) (*mcp.CallToolResult, error)) func(context.Context, mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
			start := time.Now()
			agent := "unknown"
			projectID := "default"
			if args, ok := req.Params.Arguments.(map[string]any); ok {
				if a, ok := args["_agent"].(string); ok {
					agent = a
				}
				if p, ok := args["_project"].(string); ok {
					projectID = p
				}
			}

			// RBAC Check
			allowed, err := h.db.CheckPermission(agent, toolName)
			if err != nil || !allowed {
				if toolName == "security_fix" || toolName == "council_execute" {
					return mcp.NewToolResultError("Operation requires higher privileges. Proposal created."), nil
				}
				return mcp.NewToolResultError("Permission denied for tool: " + toolName), nil
			}

			res, err := hdlr(ctx, req)
			
			// Record Metric
			duration := time.Since(start)
			h.db.RecordMetric(toolName, agent, projectID, duration, err == nil)
			
			return res, err
		}
	}

	// --- Skills Tools ---
	s.AddTool(mcp.NewTool("skills_list", mcp.WithDescription("List all available skill names.")), withRBAC("skills_list", h.listSkills))
	s.AddTool(mcp.NewTool("skills_load",
		mcp.WithDescription("Load full SKILL.md content."),
		mcp.WithString("name", mcp.Required(), mcp.Description("Skill name")),
	), withRBAC("skills_load", h.loadSkill))
	s.AddTool(mcp.NewTool("skills_search",
		mcp.WithDescription("Search skills by keyword in name or description."),
		mcp.WithString("query", mcp.Required(), mcp.Description("Search keyword")),
	), withRBAC("skills_search", h.searchSkills))

	// --- Agents Tools ---
	s.AddTool(mcp.NewTool("agents_list", mcp.WithDescription("List all specialist agents.")), withRBAC("agents_list", h.listAgents))
	s.AddTool(mcp.NewTool("agents_load",
		mcp.WithDescription("Load agent profile (persona and rules)."),
		mcp.WithString("name", mcp.Required(), mcp.Description("Agent name (e.g. orchestrator, analyst)")),
	), withRBAC("agents_load", h.loadAgent))

	// --- Knowledge Tools ---
	s.AddTool(mcp.NewTool("knowledge_read",
		mcp.WithDescription("Read core knowledge artifacts (KNOWLEDGE.md, ARCHITECTURE.md)."),
		mcp.WithString("name", mcp.Required(), mcp.Enum("KNOWLEDGE", "ARCHITECTURE")),
	), withRBAC("knowledge_read", h.readKnowledge))
	
	s.AddTool(mcp.NewTool("search_knowledge",
		mcp.WithDescription("Semantic search across project brain."),
		mcp.WithString("query", mcp.Required(), mcp.Description("Search query")),
	), withRBAC("search_knowledge", h.searchKnowledge))

	s.AddTool(mcp.NewTool("search_fulltext",
		mcp.WithDescription("Instant full-text search across project logs, docs, and tasks."),
		mcp.WithString("query", mcp.Required(), mcp.Description("Search query (supports FTS5 syntax)")),
	), withRBAC("search_fulltext", h.searchFullText))

	// --- Infrastructure & Ops ---
	s.AddTool(mcp.NewTool("backup_s3",
		mcp.WithDescription("Backup SQLite database to S3/SeaweedFS."),
		mcp.WithString("bucket", mcp.Required(), mcp.Description("S3 Bucket name")),
		mcp.WithString("endpoint", mcp.Required(), mcp.Description("S3 Endpoint URL")),
	), withRBAC("backup_s3", h.backupS3))
	
	s.AddTool(mcp.NewTool("webhook_register",
		mcp.WithDescription("Register an outbound webhook for system events."),
		mcp.WithString("url", mcp.Required(), mcp.Description("Webhook URL")),
		mcp.WithString("events", mcp.Required(), mcp.Description("Comma-separated events")),
	), withRBAC("webhook_register", h.registerWebhook))
	
	s.AddTool(mcp.NewTool("metrics_get",
		mcp.WithDescription("Retrieve tool execution performance metrics."),
	), withRBAC("metrics_get", h.getMetrics))
	
	s.AddTool(mcp.NewTool("health_check",
		mcp.WithDescription("Run workspace health report."),
	), withRBAC("health_check", h.healthCheck))

	s.AddTool(mcp.NewTool("health_fix",
		mcp.WithDescription("Automatically repair workspace structure and permissions."),
	), withRBAC("health_fix", h.healthFix))

	s.AddTool(mcp.NewTool("project_list", mcp.WithDescription("List all registered projects.")), withRBAC("project_list", h.listProjects))
	
	s.AddTool(mcp.NewTool("graph_get",
		mcp.WithDescription("Get the agent interaction graph for the current session."),
	), withRBAC("graph_get", h.getGraph))

	s.AddTool(mcp.NewTool("system_info",
		mcp.WithDescription("Get basic system information."),
	), withRBAC("system_info", h.systemInfo))

	s.AddTool(mcp.NewTool("secrets_set",
		mcp.WithDescription("Securely store a secret key-value pair."),
		mcp.WithString("key", mcp.Required(), mcp.Description("Secret key")),
		mcp.WithString("value", mcp.Required(), mcp.Description("Secret value")),
	), withRBAC("secrets_set", h.setSecret))

	s.AddTool(mcp.NewTool("secrets_get",
		mcp.WithDescription("Retrieve a securely stored secret value."),
		mcp.WithString("key", mcp.Required(), mcp.Description("Secret key")),
	), withRBAC("secrets_get", h.getSecret))

	// --- Resource Hooks ---
	s.AddTool(mcp.NewTool("hook_register",
		mcp.WithDescription("Register a resource hook (on_read or on_change)."),
		mcp.WithString("uri", mcp.Required(), mcp.Description("Resource path (relative) or '*' for all")),
		mcp.WithString("event", mcp.Required(), mcp.Description("Event type: on_read | on_change")),
		mcp.WithString("script", mcp.Required(), mcp.Description("Path to the script to execute")),
	), withRBAC("hook_register", h.registerHook))
	
	s.AddTool(mcp.NewTool("hook_list",
		mcp.WithDescription("List all active resource hooks."),
	), withRBAC("hook_list", h.listHooks))

	s.AddTool(mcp.NewTool("hook_remove",
		mcp.WithDescription("Remove a resource hook."),
		mcp.WithString("uri", mcp.Required(), mcp.Description("Resource path")),
		mcp.WithString("event", mcp.Required(), mcp.Description("Event type")),
	), withRBAC("hook_remove", h.removeHook))

	// --- Jobs & Workflows ---
	s.AddTool(mcp.NewTool("jobs_list", mcp.WithDescription("List all active and recent background jobs.")), withRBAC("jobs_list", h.listJobs))
	s.AddTool(mcp.NewTool("jobs_status",
		mcp.WithDescription("Get status of a specific job."),
		mcp.WithString("id", mcp.Required(), mcp.Description("Job ID")),
	), withRBAC("jobs_status", h.getJobStatus))
	
	s.AddTool(mcp.NewTool("workflows_list", mcp.WithDescription("List available automation workflows.")), withRBAC("workflows_list", h.listWorkflows))
	s.AddTool(mcp.NewTool("workflows_run",
		mcp.WithDescription("Execute a workflow safely."),
		mcp.WithString("name", mcp.Required(), mcp.Description("Workflow name")),
		mcp.WithString("arguments", mcp.Required(), mcp.Description("Arguments to pass")),
	), withRBAC("workflows_run", h.runWorkflow))

	s.AddTool(mcp.NewTool("tasks_submit",
		mcp.WithDescription("Submit a new task to the backlog."),
		mcp.WithString("title", mcp.Required(), mcp.Description("Task title")),
		mcp.WithString("description", mcp.Required(), mcp.Description("Task details")),
		mcp.WithString("agent", mcp.Required(), mcp.Description("Target specialist agent")),
	), withRBAC("tasks_submit", h.submitTask))

	// --- Logging & Observability ---
	s.AddTool(mcp.NewTool("logs_tail",
		mcp.WithDescription("Get recent agent execution logs."),
		mcp.WithNumber("lines", mcp.Description("Number of lines to return (default 20)")),
	), withRBAC("logs_tail", h.tailLogs))

	s.AddTool(mcp.NewTool("analytics_get",
		mcp.WithDescription("Get performance metrics for agents and workflows."),
	), withRBAC("analytics_get", h.getAnalytics))

	// --- Architecture & Status ---

	s.AddTool(mcp.NewTool("bmad_status", mcp.WithDescription("Check the status of the BMAD lifecycle.")), withRBAC("bmad_status", h.bmadStatus))
	s.AddTool(mcp.NewTool("status_summary", mcp.WithDescription("Get Agent Kit summary.")), withRBAC("status_summary", h.statusSummary))

	// --- Council of Sages ---
	s.AddTool(mcp.NewTool("council_list", mcp.WithDescription("List all active council proposals.")), withRBAC("council_list", h.listProposals))
	s.AddTool(mcp.NewTool("council_vote",
		mcp.WithDescription("Vote on a council proposal."),
		mcp.WithString("id", mcp.Required(), mcp.Description("Proposal ID")),
	), withRBAC("council_vote", h.voteProposal))
	s.AddTool(mcp.NewTool("council_propose",
		mcp.WithDescription("Create a new council proposal."),
		mcp.WithString("title", mcp.Required(), mcp.Description("Proposal title")),
	), withRBAC("council_propose", h.createProposal))
	s.AddTool(mcp.NewTool("council_execute",
		mcp.WithDescription("Trigger execution of an approved proposal."),
		mcp.WithString("id", mcp.Required(), mcp.Description("Proposal ID")),
	), withRBAC("council_execute", h.executeProposal))

	s.AddTool(mcp.NewTool("council_set_permission",
		mcp.WithDescription("Set tool permission for an agent."),
		mcp.WithString("agent", mcp.Required(), mcp.Description("Agent name")),
		mcp.WithString("tool", mcp.Required(), mcp.Description("Tool name")),
		mcp.WithBoolean("allowed", mcp.Required(), mcp.Description("Allow or deny")),
	), withRBAC("council_set_permission", h.setPermission))

	s.AddTool(mcp.NewTool("security_fix",
		mcp.WithDescription("Trigger an agent to automatically fix a security vulnerability."),
		mcp.WithString("vulnerability_id", mcp.Required(), mcp.Description("ID of vulnerability")),
		mcp.WithString("file_path", mcp.Required(), mcp.Description("File to patch")),
	), withRBAC("security_fix", h.securityFix))

	// --- BMAD Automation ---
	s.AddTool(mcp.NewTool("bmad_decompose",
		mcp.WithDescription("Decompose a PRD into story cards."),
		mcp.WithString("prd_path", mcp.Required(), mcp.Description("Path to PRD file")),
	), withRBAC("bmad_decompose", h.decomposePRD))

	if *mode == "stdio" {
		server.ServeStdio(s)
	} else {
		addr := ":" + *port
		fmt.Fprintf(os.Stderr, "MCP Server listening on %s\n", addr)

		// Health endpoint for Kubernetes liveness/readiness probes.
		http.HandleFunc("/health", func(w http.ResponseWriter, _ *http.Request) {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusOK)
			fmt.Fprintf(w, `{"status":"ok","version":"%s"}`, serverVersion)
		})

		mcpHandler := loggingMiddleware(server.NewSSEServer(s))
		http.Handle("/mcp", mcpHandler)
		http.Handle("/mcp/", mcpHandler)
		
		// SSE log streaming — tail audit.log
		auditLogPath := filepath.Join(h.projectRoot, "audit.log")
		http.HandleFunc("/logs/stream", func(w http.ResponseWriter, r *http.Request) {
			w.Header().Set("Content-Type", "text/event-stream")
			w.Header().Set("Cache-Control", "no-cache")
			w.Header().Set("Connection", "keep-alive")
			flusher, ok := w.(http.Flusher)
			if !ok {
				http.Error(w, "streaming not supported", http.StatusInternalServerError)
				return
			}
			data, err := os.ReadFile(auditLogPath)
			if err != nil {
				fmt.Fprintf(w, "data: audit.log not found\n\n")
				flusher.Flush()
				return
			}
			lines := strings.Split(strings.TrimRight(string(data), "\n"), "\n")
			start := len(lines) - 100
			if start < 0 {
				start = 0
			}
			for _, line := range lines[start:] {
				fmt.Fprintf(w, "data: %s\n\n", line)
				flusher.Flush()
			}
		})

		// Graceful shutdown
		srv := &http.Server{Addr: addr}
		go func() {
			if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
				fmt.Fprintf(os.Stderr, "listen: %s\n", err)
			}
		}()

		quit := make(chan os.Signal, 1)
		signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
		<-quit
		fmt.Fprintf(os.Stderr, "Shutting down server...\n")
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		if err := srv.Shutdown(ctx); err != nil {
			fmt.Fprintf(os.Stderr, "Server forced to shutdown: %v\n", err)
		}
	}
}
