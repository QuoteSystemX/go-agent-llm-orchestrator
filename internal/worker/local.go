package worker

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"go-agent-llm-orchestrator/internal/db"
	"go-agent-llm-orchestrator/internal/llm"
	"go-agent-llm-orchestrator/internal/monitor"
	"github.com/mark3labs/mcp-go/client"
	"github.com/mark3labs/mcp-go/mcp"
)

type LocalExecutor struct {
	db      *db.DB
	router  *llm.Router
	tracer  monitor.Tracer
	mcpPath string
	
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
		mcpPath:  mcpPath,
		sessions: make(map[string]*localSession),
	}
}

func (e *LocalExecutor) SetTracer(t monitor.Tracer) {
	e.tracer = t
}

func (e *LocalExecutor) Execute(ctx context.Context, task *db.Task, prompt string) (string, error) {
	sessionID := fmt.Sprintf("local-%s-%d", task.ID, time.Now().Unix())
	
	sessionCtx, cancel := context.WithCancel(context.Background())
	sess := &localSession{
		status: "RUNNING",
		cancel: cancel,
	}
	
	e.sessionsMu.Lock()
	e.sessions[sessionID] = sess
	e.sessionsMu.Unlock()
	
	// В автономном режиме Execute должен быть синхронным для планировщика, 
	// так как Engine.runTask уже запускается в горутине.
	e.runLoop(sessionCtx, sessionID, task, prompt)
	
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

func (e *LocalExecutor) runLoop(ctx context.Context, sessionID string, task *db.Task, initialPrompt string) {
	defer func() {
		if r := recover(); r != nil {
			log.Printf("Session %s panicked: %v", sessionID, r)
			e.updateSession(sessionID, "FAILED", "", fmt.Errorf("panic: %v", r))
		}
	}()

	log.Printf("Session %s: Starting local agent loop for task %s", sessionID, task.ID)
	
	// 1. Start MCP Server
	mcpClient, err := e.startMCPServer(ctx)
	if err != nil {
		log.Printf("Session %s: Failed to start MCP server: %v", sessionID, err)
		e.updateSession(sessionID, "FAILED", "", err)
		return
	}
	defer mcpClient.Close()
	
	// 2. Fetch Tools
	tools, err := mcpClient.ListTools(ctx, mcp.ListToolsRequest{})
	if err != nil {
		log.Printf("Session %s: Failed to list MCP tools: %v", sessionID, err)
		e.updateSession(sessionID, "FAILED", "", err)
		return
	}
	
	log.Printf("Session %s: MCP server ready with %d tools", sessionID, len(tools.Tools))

	// 3. ReAct Loop
	history := []llm.Message{
		{Role: "system", Content: fmt.Sprintf("You are an autonomous agent specialized in %s. Your mission: %s", task.Agent, task.Mission)},
		{Role: "user", Content: initialPrompt},
	}
	
	maxSteps := 20
	for i := 0; i < maxSteps; i++ {
		select {
		case <-ctx.Done():
			return
		default:
		}
		
		log.Printf("Session %s: Step %d/%d", sessionID, i+1, maxSteps)
		
		// Call Ollama
		resp, err := e.router.GenerateChat(ctx, llm.Complex, history, tools.Tools, "local")
		if err != nil {
			log.Printf("Session %s: LLM error: %v", sessionID, err)
			e.updateSession(sessionID, "FAILED", "", err)
			return
		}
		
		if resp.Content != "" && e.tracer != nil {
			e.tracer.BroadcastTrace(monitor.AgentTraceEvent{
				TaskID:    task.ID,
				Type:      monitor.TraceThought,
				Content:   resp.Content,
				Timestamp: time.Now(),
			})
		}

		history = append(history, *resp)
		
		if len(resp.ToolCalls) == 0 {
			log.Printf("Session %s: Task completed (final answer)", sessionID)
			e.updateSession(sessionID, "COMPLETED", resp.Content, nil)
			if e.tracer != nil {
				e.tracer.BroadcastTrace(monitor.AgentTraceEvent{
					TaskID:    task.ID,
					Type:      monitor.TraceOutput,
					Content:   resp.Content,
					Timestamp: time.Now(),
				})
			}
			return
		}
		
		// Execute Tools
		for _, tc := range resp.ToolCalls {
			if e.tracer != nil {
				e.tracer.BroadcastTrace(monitor.AgentTraceEvent{
					TaskID:    task.ID,
					Type:      monitor.TraceTool,
					Content:   fmt.Sprintf("Calling tool %s(%s)", tc.Function.Name, tc.Function.Arguments),
					Timestamp: time.Now(),
				})
			}

			log.Printf("Session %s: Calling tool %s with args %s", sessionID, tc.Function.Name, tc.Function.Arguments)
			
			var args map[string]any
			if err := json.Unmarshal([]byte(tc.Function.Arguments), &args); err != nil {
				log.Printf("Session %s: Failed to parse tool arguments: %v", sessionID, err)
				history = append(history, llm.Message{Role: "tool", Content: fmt.Sprintf("Error parsing arguments: %v", err), ToolID: tc.ID})
				continue
			}

			result, err := mcpClient.CallTool(ctx, mcp.CallToolRequest{
				Params: mcp.CallToolParams{
					Name: tc.Function.Name,
					Arguments: func() map[string]any {
						args["_agent"] = task.Agent
						args["_project"] = task.Name
						return args
					}(),
				},
			})
			
			var observation string
			if err != nil {
				observation = fmt.Sprintf("Error calling tool %s: %v", tc.Function.Name, err)
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
			
			if e.tracer != nil {
				e.tracer.BroadcastTrace(monitor.AgentTraceEvent{
					TaskID:    task.ID,
					Type:      monitor.TraceTool,
					Content:   fmt.Sprintf("Tool %s returned observation", tc.Function.Name),
					Metadata:  observation,
					Timestamp: time.Now(),
				})
			}

			history = append(history, llm.Message{Role: "tool", Content: observation, ToolID: tc.ID})
		}
	}
	
	e.updateSession(sessionID, "FAILED", "", fmt.Errorf("reached max steps (%d) without completion", maxSteps))
}

func (e *LocalExecutor) startMCPServer(ctx context.Context) (*client.Client, error) {
	binPath := filepath.Join(e.mcpPath, "bin", "mcp-server")
	os.MkdirAll(filepath.Dir(binPath), 0755)

	if _, err := os.Stat(binPath); os.IsNotExist(err) {
		log.Printf("MCP binary missing at %s, attempting to build...", binPath)
		buildCmd := exec.CommandContext(ctx, "go", "build", "-o", binPath, "main.go")
		buildCmd.Dir = e.mcpPath
		buildCmd.Stdout = os.Stdout
		buildCmd.Stderr = os.Stderr
		if err := buildCmd.Run(); err != nil {
			log.Printf("MCP build failed: %v, falling back to 'go run'", err)
			return client.NewStdioMCPClient("go", []string{}, "run", filepath.Join(e.mcpPath, "main.go"))
		}
	}
	
	return client.NewStdioMCPClient(binPath, []string{})
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
