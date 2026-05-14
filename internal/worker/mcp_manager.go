package worker

import (
	"context"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"sync"

	"github.com/mark3labs/mcp-go/client"
)

// MCPResourceManager manages the lifecycle of MCP servers.
type MCPResourceManager struct {
	mcpPath string
	binPath string
	
	buildMu sync.Mutex
	isBuilt bool
}

func NewMCPResourceManager(mcpPath string) *MCPResourceManager {
	return &MCPResourceManager{
		mcpPath: mcpPath,
		binPath: filepath.Join(mcpPath, "bin", "mcp-server"),
	}
}

// GetClient returns a new MCP client. It builds the server binary if necessary.
func (m *MCPResourceManager) GetClient(ctx context.Context) (*client.Client, error) {
	if err := m.ensureBuilt(ctx); err != nil {
		return nil, err
	}
	
	return client.NewStdioMCPClient(m.binPath, []string{})
}

func (m *MCPResourceManager) ensureBuilt(ctx context.Context) error {
	m.buildMu.Lock()
	defer m.buildMu.Unlock()
	
	if m.isBuilt {
		return nil
	}
	
	// Check if file already exists
	if _, err := os.Stat(m.binPath); err == nil {
		m.isBuilt = true
		return nil
	}
	
	log.Printf("MCP Manager: Building server binary at %s...", m.binPath)
	os.MkdirAll(filepath.Dir(m.binPath), 0755)
	
	buildCmd := exec.CommandContext(ctx, "go", "build", "-o", m.binPath, "main.go")
	buildCmd.Dir = m.mcpPath
	// We capture output to avoid polluting logs unless there's an error
	output, err := buildCmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("MCP build failed: %v, output: %s", err, string(output))
	}
	
	log.Printf("MCP Manager: Server built successfully")
	m.isBuilt = true
	return nil
}
