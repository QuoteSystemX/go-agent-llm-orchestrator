package worker

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"strings"
	"sync"
	"time"

	"go-agent-llm-orchestrator/internal/db"
	"go-agent-llm-orchestrator/internal/llm"
	"go-agent-llm-orchestrator/internal/monitor"
	"github.com/mark3labs/mcp-go/mcp"
)

// SessionIndexer defines the interface for vectorizing session history.
type SessionIndexer interface {
	IndexSession(ctx context.Context, repoName, sessionID, content string) error
}

type LocalExecutor struct {
	db       *db.DB
	router   *llm.Router
	tracer   monitor.Tracer
	mcpMgr   *MCPResourceManager
	indexer  SessionIndexer
	
	sessions   map[string]*localSession
	sessionsMu sync.Mutex
}

type localSession struct {
	status    string
	result    string
	err       error
	cancel    context.CancelFunc
}

func NewLocalExecutor(database *db.DB, router *llm.Router, mcpPath string) *LocalExecutor {
	return &LocalExecutor{
		db:       database,
		router:   router,
		mcpMgr:   NewMCPResourceManager(mcpPath),
		sessions: make(map[string]*localSession),
	}
}

func (e *LocalExecutor) SetTracer(t monitor.Tracer) {
	e.tracer = t
}

func (e *LocalExecutor) SetIndexer(i SessionIndexer) {
	e.indexer = i
}

func (e *LocalExecutor) Execute(ctx context.Context, task *db.Task, prompt string, logID int64) (string, error) {
	sessionID := fmt.Sprintf("local-%s-%d", task.ID, time.Now().Unix())
	
	sessionCtx, cancel := context.WithCancel(context.Background())
	sess := &localSession{
		status: "RUNNING",
		cancel: cancel,
	}
	
	e.sessionsMu.Lock()
	e.sessions[sessionID] = sess
	e.sessionsMu.Unlock()
	
	// Execute ReAct Loop
	e.runLoop(sessionCtx, sessionID, task, prompt, logID)
	
	return sessionID, sess.err
}

func (e *LocalExecutor) GetStatus(ctx context.Context, sessionID string) (string, error) {
	e.sessionsMu.Lock()
	defer e.sessionsMu.Unlock()
	
	sess, ok := e.sessions[sessionID]
	if !ok {
		return "", fmt.Errorf("session %s not found", sessionID)
	}
	return sess.status, nil
}

func (e *LocalExecutor) Cancel(ctx context.Context, sessionID string) error {
	e.sessionsMu.Lock()
	defer e.sessionsMu.Unlock()
	
	sess, ok := e.sessions[sessionID]
	if !ok {
		return nil
	}
	sess.cancel()
	sess.status = "CANCELLED"
	return nil
}

func (e *LocalExecutor) runLoop(ctx context.Context, sessionID string, task *db.Task, initialPrompt string, logID int64) {
	defer func() {
		if r := recover(); r != nil {
			log.Printf("Session %s panicked: %v", sessionID, r)
			e.updateSession(sessionID, "FAILED", "", fmt.Errorf("panic: %v", r))
		}
	}()

	log.Printf("Session %s: Starting local agent loop for task %s", sessionID, task.ID)
	
	// Start MCP Server via Manager
	mcpClient, err := e.mcpMgr.GetClient(ctx)
	if err != nil {
		log.Printf("Session %s: Failed to get MCP client: %v", sessionID, err)
		e.updateSession(sessionID, "FAILED", "", err)
		return
	}
	defer mcpClient.Close()
	
	tools, err := mcpClient.ListTools(ctx, mcp.ListToolsRequest{})
	if err != nil {
		log.Printf("Session %s: Failed to list MCP tools: %v", sessionID, err)
		e.updateSession(sessionID, "FAILED", "", err)
		return
	}

	history := []llm.Message{
		{Role: "system", Content: fmt.Sprintf("You are an autonomous agent specialized in %s. Your mission: %s", task.Agent, task.Mission)},
		{Role: "user", Content: initialPrompt},
	}
	
	// Get max steps from settings or use default
	maxSteps := 20
	if val := e.db.GetSetting("agent_max_steps", "20"); val != "" {
		fmt.Sscanf(val, "%d", &maxSteps)
	}

	for i := 0; i < maxSteps; i++ {
		select {
		case <-ctx.Done():
			return
		default:
		}
		
		stepStart := time.Now()
		resp, err := e.router.GenerateChat(ctx, llm.Complex, history, tools.Tools, "local")
		if err != nil {
			log.Printf("Session %s: LLM error: %v", sessionID, err)
			e.updateSession(sessionID, "FAILED", "", err)
			return
		}
		
		if resp.Content != "" {
			// Persistence: Save thought
			if logID > 0 {
				e.db.AddTaskRunDetail(ctx, logID, "THOUGHT", resp.Content, time.Since(stepStart).Milliseconds())
			}
			// WebSocket Trace
			if e.tracer != nil {
				e.tracer.BroadcastTrace(monitor.AgentTraceEvent{
					TaskID:    task.ID,
					Type:      monitor.TraceThought,
					Content:   resp.Content,
					Timestamp: time.Now(),
				})
			}
		}

		history = append(history, *resp)
		
		if len(resp.ToolCalls) == 0 {
			e.updateSession(sessionID, "COMPLETED", resp.Content, nil)
			if logID > 0 {
				e.db.AddTaskRunDetail(ctx, logID, "OUTPUT", resp.Content, time.Since(stepStart).Milliseconds())
			}
			if e.tracer != nil {
				e.tracer.BroadcastTrace(monitor.AgentTraceEvent{
					TaskID:    task.ID,
					Type:      monitor.TraceOutput,
					Content:   resp.Content,
					Timestamp: time.Now(),
				})
			}
			
			// Vectorize session history for long-term memory
			if e.indexer != nil {
				go func() {
					fullHistory, _ := json.Marshal(history)
					if err := e.indexer.IndexSession(context.Background(), task.Name, sessionID, string(fullHistory)); err != nil {
						log.Printf("Session %s: Failed to index session history: %v", sessionID, err)
					} else {
						log.Printf("Session %s: History vectorized for long-term memory", sessionID)
					}
				}()
			}
			
			return
		}
		
		// Execute Tools
		for _, tc := range resp.ToolCalls {
			toolStart := time.Now()
			
			// Audit Log: Record tool call
			e.db.AddAuditLog(ctx, sessionID, "TOOL_CALL", fmt.Sprintf("%s(%s)", tc.Function.Name, tc.Function.Arguments))

			if e.tracer != nil {
				e.tracer.BroadcastTrace(monitor.AgentTraceEvent{
					TaskID:    task.ID,
					Type:      monitor.TraceTool,
					Content:   fmt.Sprintf("Calling tool %s(%s)", tc.Function.Name, tc.Function.Arguments),
					Timestamp: time.Now(),
				})
			}

			var args map[string]any
			_ = json.Unmarshal([]byte(tc.Function.Arguments), &args)

			result, err := mcpClient.CallTool(ctx, mcp.CallToolRequest{
				Params: mcp.CallToolParams{
					Name: tc.Function.Name,
					Arguments: func() map[string]any {
						if args == nil { args = make(map[string]any) }
						args["_agent"] = task.Agent
						args["_project"] = task.Name
						return args
					}(),
				},
			})
			
			var observation string
			if err != nil {
				observation = fmt.Sprintf("Error: %v", err)
			} else {
				var sb strings.Builder
				for _, content := range result.Content {
					if text, ok := content.(mcp.TextContent); ok {
						sb.WriteString(text.Text)
					} else {
						sb.WriteString(fmt.Sprintf("%v", content))
					}
				}
				observation = sb.String()
			}
			
			// Token Truncation logic (SRE recommendation)
			const maxObservationSize = 8000
			if len(observation) > maxObservationSize {
				observation = observation[:maxObservationSize] + "\n... (truncated for context limit)"
			}

			// Persistence: Save tool result
			if logID > 0 {
				e.db.AddTaskRunDetail(ctx, logID, "TOOL_RESULT", fmt.Sprintf("Tool: %s\nResult: %s", tc.Function.Name, observation), time.Since(toolStart).Milliseconds())
			}

			if e.tracer != nil {
				e.tracer.BroadcastTrace(monitor.AgentTraceEvent{
					TaskID:    task.ID,
					Type:      monitor.TraceTool,
					Content:   fmt.Sprintf("Tool %s returned observation", tc.Function.Name),
					Metadata:  observation,
					Timestamp: time.Now(),
				})
			}

			// Handover detection
			if strings.HasPrefix(observation, "TRANSFERRED:") {
				newAgent := strings.TrimSpace(strings.TrimPrefix(observation, "TRANSFERRED:"))
				if idx := strings.Index(newAgent, "."); idx != -1 {
					newAgent = newAgent[:idx]
				}
				newAgent = strings.TrimSpace(strings.TrimPrefix(newAgent, "Agent changed to "))
				
				log.Printf("Session %s: HANDOVER detected. Transferring to agent %s", sessionID, newAgent)
				e.db.AddAuditLog(ctx, sessionID, "HANDOVER", fmt.Sprintf("Task transferred from %s to %s", task.Agent, newAgent))
				
				task.Agent = newAgent
				// Update system prompt for next step
				history[0].Content = fmt.Sprintf("You are an autonomous agent specialized in %s. Your mission: %s", task.Agent, task.Mission)
				
				if logID > 0 {
					e.db.AddTaskRunDetail(ctx, logID, "HANDOVER", fmt.Sprintf("Transferred to agent: %s", newAgent), 0)
				}
			}

			// Approval Gate & Red Team Audit
			if strings.Contains(observation, "intercepted") || strings.Contains(observation, "require council approval") {
				log.Printf("Session %s: APPROVAL REQUIRED detected. Running Red Team audit...", sessionID)
				
				audit, err := e.router.RedTeamAudit(ctx, fmt.Sprintf("Action: %s(%s)", tc.Function.Name, tc.Function.Arguments), observation)
				if err == nil {
					if e.tracer != nil {
						e.tracer.BroadcastTrace(monitor.AgentTraceEvent{
							TaskID:    task.ID,
							Type:      monitor.TraceThought,
							Content:   "🔴 RED TEAM AUDIT: " + audit,
							Timestamp: time.Now(),
						})
					}
					if logID > 0 {
						e.db.AddTaskRunDetail(ctx, logID, "RED_TEAM_AUDIT", audit, 0)
					}
					// Pause task and save audit to pending_decision
					e.db.Exec("UPDATE tasks SET status = 'WAITING_APPROVAL', pending_decision = ? WHERE id = ?", audit, task.ID)
					e.updateSession(sessionID, "WAITING_APPROVAL", audit, nil)
					return // Pause execution
				}
			}

			history = append(history, llm.Message{Role: "tool", Content: observation, ToolID: tc.ID})
		}
	}
	
	e.updateSession(sessionID, "FAILED", "", fmt.Errorf("reached max steps (%d) without completion", maxSteps))
}

func (e *LocalExecutor) updateSession(id, status, result string, err error) {
	e.sessionsMu.Lock()
	if sess, ok := e.sessions[id]; ok {
		sess.status = status
		sess.result = result
		sess.err = err
	}
	e.sessionsMu.Unlock()
	
	if e.db != nil {
		_, _ = e.db.Exec("UPDATE sessions SET status = ? WHERE id = ?", status, id)
	}
}
