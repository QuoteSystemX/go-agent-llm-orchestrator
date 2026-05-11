package main

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"time"
	"sync"

	"github.com/mark3labs/mcp-go/mcp"
)

type LSPManager struct {
	projectRoot string
	servers     map[string]*lspClient
	mu          sync.Mutex
}

type lspClient struct {
	process *os.Process
	cmd    *exec.Cmd
	stdin  io.WriteCloser
	stdout *bufio.Reader
	mu     sync.Mutex
	id     int
}

func NewLSPManager(root string) *LSPManager {
	return &LSPManager{
		projectRoot: root,
		servers:     make(map[string]*lspClient),
	}
}

func (m *LSPManager) log(format string, v ...interface{}) {
	f, err := os.OpenFile("lsp_debug.log", os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err == nil {
		defer f.Close()
		fmt.Fprintf(f, "[%s] "+format+"\n", append([]interface{}{time.Now().Format(time.RFC3339)}, v...)...)
	}
	fmt.Fprintf(os.Stderr, format+"\n", v...)
}

func (m *LSPManager) Close() {
	m.mu.Lock()
	defer m.mu.Unlock()
	for lang, client := range m.servers {
		m.log("Closing LSP client for %s", lang)
		if client.process != nil {
			client.process.Kill()
		}
	}
}

func (m *LSPManager) getClient(lang string) (*lspClient, error) {
	m.mu.Lock()
	if client, ok := m.servers[lang]; ok {
		m.mu.Unlock()
		return client, nil
	}
	m.mu.Unlock()

	m.log("Spawning LSP server for %s", lang)
	var cmdPath string
	var args []string

	switch lang {
	case "go":
		cmdPath = "gopls"
		args = []string{"serve"}
	case "markdown":
		cmdPath = "marksman"
		args = []string{"server"}
	case "typescript", "typescriptreact":
		cmdPath = "typescript-language-server"
		args = []string{"--stdio"}
	default:
		return nil, fmt.Errorf("unsupported language: %s", lang)
	}

	cmd := exec.Command(cmdPath, args...)
	cmd.Stderr = os.Stderr
	stdin, err := cmd.StdinPipe()
	if err != nil {
		return nil, err
	}
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return nil, err
	}

	if err := cmd.Start(); err != nil {
		return nil, err
	}

	client := &lspClient{
		process: cmd.Process,
		stdin:   stdin,
		stdout:  bufio.NewReader(stdout),
	}

	m.log("Initializing LSP server for %s...", lang)
	if err := client.initialize(m.projectRoot); err != nil {
		client.process.Kill()
		return nil, fmt.Errorf("failed to initialize LSP for %s: %v", lang, err)
	}

	m.mu.Lock()
	m.servers[lang] = client
	m.mu.Unlock()
	m.log("LSP server for %s is ready", lang)

	return client, nil
}

func (c *lspClient) initialize(root string) error {
	params := map[string]interface{}{
		"processId": os.Getpid(),
		"rootUri":   "file://" + root,
		"workspaceFolders": []map[string]interface{}{
			{
				"uri":  "file://" + root,
				"name": filepath.Base(root),
			},
		},
		"capabilities": map[string]interface{}{
			"textDocument": map[string]interface{}{
				"definition": map[string]interface{}{"dynamicRegistration": true},
				"hover":      map[string]interface{}{"dynamicRegistration": true},
			},
			"workspace": map[string]interface{}{
				"configuration": true,
			},
		},
	}
	_, err := c.call("initialize", params)
	if err != nil {
		return err
	}

	// Send initialized notification (no ID, no response expected)
	return c.notify("initialized", map[string]interface{}{})
}

func (c *lspClient) notify(method string, params interface{}) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	req := map[string]interface{}{
		"jsonrpc": "2.0",
		"method":  method,
		"params":  params,
	}

	data, err := json.Marshal(req)
	if err != nil {
		return err
	}

	payload := fmt.Sprintf("Content-Length: %d\r\n\r\n%s", len(data), data)
	_, err = c.stdin.Write([]byte(payload))
	return err
}

func (c *lspClient) call(method string, params interface{}) (json.RawMessage, error) {
	c.mu.Lock()
	defer c.mu.Unlock()

	c.id++
	req := map[string]interface{}{
		"jsonrpc": "2.0",
		"id":      c.id,
		"method":  method,
		"params":  params,
	}

	data, err := json.Marshal(req)
	if err != nil {
		return nil, err
	}

	payload := fmt.Sprintf("Content-Length: %d\r\n\r\n%s", len(data), data)
	if _, err := c.stdin.Write([]byte(payload)); err != nil {
		return nil, err
	}

	// Read response
	line, err := c.stdout.ReadString('\n')
	if err != nil {
		return nil, err
	}

	if !strings.HasPrefix(line, "Content-Length:") {
		return nil, fmt.Errorf("invalid LSP response header: %s", line)
	}

	lenStr := strings.TrimSpace(strings.TrimPrefix(line, "Content-Length:"))
	contentLen, err := strconv.Atoi(lenStr)
	if err != nil {
		return nil, err
	}

	// Skip empty line
	_, _ = c.stdout.ReadString('\n')

	body := make([]byte, contentLen)
	if _, err := io.ReadFull(c.stdout, body); err != nil {
		return nil, err
	}

	var resp struct {
		Result json.RawMessage `json:"result"`
		Error  interface{}     `json:"error"`
	}
	if err := json.Unmarshal(body, &resp); err != nil {
		return nil, err
	}

	if resp.Error != nil {
		return nil, fmt.Errorf("LSP error: %v", resp.Error)
	}

	return resp.Result, nil
}

// --- MCP Handlers ---

func (h *handler) semanticDefinition(_ context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	args, _ := req.Params.Arguments.(map[string]interface{})
	file, _ := args["file"].(string)
	lineVal, _ := args["line"].(float64)
	charVal, _ := args["char"].(float64)

	lang := "go"
	if strings.HasSuffix(file, ".md") {
		lang = "markdown"
	} else if strings.HasSuffix(file, ".ts") {
		lang = "typescript"
	} else if strings.HasSuffix(file, ".tsx") {
		lang = "typescriptreact"
	}

	client, err := h.lsp.getClient(lang)
	if err != nil {
		return mcp.NewToolResultError("LSP client error: " + err.Error()), nil
	}

	params := map[string]interface{}{
		"textDocument": map[string]interface{}{
			"uri": "file://" + filepath.Join(h.projectRoot, file),
		},
		"position": map[string]interface{}{
			"line":      int(lineVal),
			"character": int(charVal),
		},
	}

	res, err := client.call("textDocument/definition", params)
	if err != nil {
		return mcp.NewToolResultError("LSP call error: " + err.Error()), nil
	}

	return mcp.NewToolResultText(string(res)), nil
}

func (h *handler) semanticHover(_ context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	args, _ := req.Params.Arguments.(map[string]interface{})
	file, _ := args["file"].(string)
	lineVal, _ := args["line"].(float64)
	charVal, _ := args["char"].(float64)

	lang := "go"
	if strings.HasSuffix(file, ".md") {
		lang = "markdown"
	} else if strings.HasSuffix(file, ".ts") {
		lang = "typescript"
	} else if strings.HasSuffix(file, ".tsx") {
		lang = "typescriptreact"
	}

	client, err := h.lsp.getClient(lang)
	if err != nil {
		return mcp.NewToolResultError("LSP client error: " + err.Error()), nil
	}

	params := map[string]interface{}{
		"textDocument": map[string]interface{}{
			"uri": "file://" + filepath.Join(h.projectRoot, file),
		},
		"position": map[string]interface{}{
			"line":      int(lineVal),
			"character": int(charVal),
		},
	}

	res, err := client.call("textDocument/hover", params)
	if err != nil {
		return mcp.NewToolResultError("LSP call error: " + err.Error()), nil
	}

	return mcp.NewToolResultText(string(res)), nil
}
