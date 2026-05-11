# Local Skill Server (Agentic MCP)

A lightweight Model Context Protocol (MCP) server designed to bridge the gap between AI agents and the local workspace. It provides tools for discovering skills, managing agents, executing workflows, and tracking task progress.

## 🚀 Features

- **Skill Discovery**: Instant access to all available skills in the `.agent/skills/` directory.
- **Agent Management**: Load and inspect specialist agent profiles from `.agent/agents/`.
- **Workflow Execution**: Run automation patterns and system scripts safely.
- **Task Backlog**: Submit new engineering tasks directly to the `tasks/` directory.
- **Project Intelligence**: Access core knowledge artifacts (`KNOWLEDGE.md`, `ARCHITECTURE.md`) and workspace health status.
- **Robust stdio Handling**: Built-in protection against stray `stdout` output to maintain JSON-RPC protocol integrity.
- **Semantic Gateway**: Integrated LSP client for high-precision code and documentation analysis (**Go, Markdown, TypeScript/React**).

## 🛠 Available Tools

### 🔍 Discovery & Agents
- `skills_list`: List all available skill names.
- `skills_load`: Load full `SKILL.md` content for a specific skill.
- `agents_list`: List all specialist agents recursively.
- `agents_load`: Load agent profile (persona and rules).

### 🏗 Lifecycle & Tasks
- `workflows_list`: List all automated workflows in `.agent/workflows/`.
- `workflows_run`: Execute a specific workflow pattern.
- `tasks_submit`: Submit a new atomic task card to the backlog.

### 🧠 Knowledge & Status
- `knowledge_read`: Read core artifacts (`KNOWLEDGE.md`, `ARCHITECTURE.md`).
- `logs_tail`: Get recent agent execution logs.
- `bmad_status`: Check the status of the BMAD lifecycle files.
- `status_summary`: Get a summary of registered agents, skills, and workflows.
- `semantic_definition`: Get the source code definition of a symbol (**Go, MD, TS, TSX**).
- `semantic_hover`: Get documentation/hover information for a symbol.

## 📦 Installation

### Prerequisites
- Go 1.26+
- Node.js 20+ (for TypeScript support)
- `make` (optional, for building)

## 🛠 LSP Dependency Setup

The Semantic Gateway requires specific language servers to be installed and available in your system PATH.

### 🍎 macOS (using Homebrew)
```bash
# Go
go install golang.org/x/tools/gopls@latest

# Markdown
brew install marksman

# TypeScript / React
npm install -g typescript-language-server typescript
```

### 🪟 Windows (using Scoop or Manual)
```powershell
# Go
go install golang.org/x/tools/gopls@latest

# Markdown
# Using Scoop:
scoop install marksman
# Or download binary from: https://github.com/artempyanykh/marksman/releases

# TypeScript / React
npm install -g typescript-language-server typescript
```

### Build
To build the server for your current platform:
```bash
cd .agent/local-skill-server
make build
```

To cross-compile for all platforms:
```bash
make build-all
```

## 🚀 Usage

The server is designed to be run as an MCP server via `stdio`. 

### Local Launcher
A convenient launcher script is provided at `./local-skill-server.sh`. It automatically detects the correct binary for your platform and resolves paths correctly even when symlinked.

### Integration with MCP Clients
Add the following to your `mcp_config.json`:

```json
{
  "mcpServers": {
    "local-skill-server": {
      "command": "/path/to/project/.agent/local-skill-server/local-skill-server.sh",
      "args": []
    }
  }
}
```

## 🏗 Architecture

The server is built using the `github.com/mark3labs/mcp-go` SDK and follows a simple, robust architecture:

1. **Stdio Isolation**: During initialization, `os.Stdout` is redirected to `os.Stderr` to prevent logs or debug prints from corrupting the JSON-RPC stream.
2. **Path Resolution**: The server automatically detects the project root by searching for the `.agent` directory.
3. **Tool Annotations**: All read-only tools (lists, loads) are explicitly marked with `readOnlyHint: true` to prevent unnecessary security prompts in modern MCP clients.

---
*Built for QuoteSystemX/prompt-library*
