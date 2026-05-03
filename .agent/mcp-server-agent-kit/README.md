# Agent Kit MCP Server (Hardened V5)

A production-grade Model Context Protocol (MCP) server that powers the Agent Kit automation framework. This server is a **Stateful Control Plane** providing persistence, managed execution, and granular governance for AI agents.

## 🚀 Features

- **Resource Hooks**: Automatic script execution triggered by file events (`on_read`, `on_change`).
- **Managed Worker Pool**: Fixed-size goroutine pool for background tasks with concurrency control.
- **Self-Healing Recovery**: Automatic resumption of interrupted jobs from the database after server restart.
- **Hardened Security (RBAC)**: Role-Based Access Control for every tool, preventing unauthorized agent actions.
- **Council Governance**: Voting-based approval mechanism for sensitive operations (security fixes, infrastructure changes).
- **Full-Text Search**: Instant search across project logs, docs, and tasks via SQLite FTS5.
- **Data Retention**: Automatic background cleanup of old jobs and metrics.
- **Production Persistence**: SQLite database with **WAL (Write-Ahead Logging)** mode for reliability.
- **Observability & Analytics**:
  - **Metrics**: Real-time performance tracking (average duration, success rates).
  - **Webhooks**: Event-driven notifications for critical system events.
  - **S3 Backups**: Automated snapshots of the database state to S3/SeaweedFS.

## 🛠 Available Tools

### 🔍 Discovery & Agents

- `skills_list`: List all available skill names in `.agent/skills/`.
- `skills_load`: Load full `SKILL.md` content for a specific skill.
- `skills_search`: Search skills by keyword in name or description.
- `agents_list`: List all specialist agents in `.agent/agents/`.
- `agents_load`: Load agent profile (persona and rules).

### 🧠 Knowledge & Intelligence

- `knowledge_read`: Read core artifacts (`KNOWLEDGE.md`, `ARCHITECTURE.md`).
- `search_knowledge`: Semantic search across project brain (requires external script).
- `search_fulltext`: Instant full-text search across logs, docs, and tasks (FTS5).
- `logs_tail`: Get recent agent execution logs from `.agent/logs/`.

### 🏗 Lifecycle & Jobs

- `workflows_list`: List available automation scripts in `.agent/scripts/`.
- `workflows_run`: Execute a workflow safely via the managed worker pool.
- `jobs_list`: List all active and recent background jobs with progress.
- `jobs_status`: Get detailed status and progress of a specific job.
- `tasks_submit`: Submit a new atomic task to the `tasks/` backlog.

### ⚖️ Governance & Security

- `council_list`: List all active and historical council proposals.
- `council_vote`: Cast a vote on a pending proposal.
- `council_propose`: Create a new council proposal for manual approval.
- `council_execute`: Trigger execution of an approved proposal.
- `council_set_permission`: Set tool-level permissions for specific agents (RBAC).
- `security_fix`: Propose a patch for a vulnerability (requires Council approval).

### 🏗 BMAD & Engineering

- `bmad_status`: Check the status of the BMAD lifecycle files in `wiki/`.
- `bmad_decompose`: Decompose a PRD into atomic story cards.
- `graph_get`: Get the agent interaction graph for the current session.

### 🛠 Infrastructure & Ops

- `health_check`: Run workspace health report and detect documentation drift.
- `health_fix`: Automatically repair workspace structure, fix script permissions, and heal documentation.
- `project_list`: List all projects registered in the current database.
- `analytics_get`: Get raw telemetry and performance analytics.
- `metrics_get`: Retrieve tool execution duration and success metrics.
- `secrets_set`: Securely store an encrypted secret key-value pair.
- `secrets_get`: Retrieve a securely stored secret value.
- `backup_s3`: Backup SQLite database to S3-compatible storage.
- `system_info`: Get basic OS and environment information.
- `status_summary`: Get a summary of registered agents and skills.
- `webhook_register`: Register outbound webhooks for system events.

### 🎣 Automation Hooks

- `hook_register`: Register a resource hook (`on_read`, `on_change`).
- `hook_list`: List all active automation hooks.
- `hook_remove`: Remove a resource hook.

## 📦 Installation & Usage

### Prerequisites

- Go 1.26+
- Python 3.x (for system scripts)
- SQLite 3

### Build

```bash
go build -o bin/mcp-server .
```

### Configuration

The server supports several CLI flags for fine-tuning:

| Flag | Description | Default |
| :--- | :--- | :--- |
| `-root` | Absolute path to the project root directory. | Auto-detected |
| `-db` | Path to the SQLite database file. | `.agent/mcp_server.db` |
| `-retention` | Data retention period in days (for jobs and metrics). | `30` |
| `-index-dirs` | Comma-separated directories to index for FTS5 search. | `.agent,wiki,tasks` |
| `-mode` | Transport mode: `stdio` (standard) or `http` (SSE). | `stdio` |
| `-port` | HTTP port for the SSE server (only if `-mode=http`). | `3200` |

#### Example `mcp_config.json`

```json
{
  "mcpServers": {
    "agent-kit": {
      "command": "/path/to/bin/mcp-server",
      "args": [
        "-root", "/home/user/project",
        "-db", "/home/user/.mcp/state.db",
        "-retention", "14",
        "-index-dirs", ".agent,wiki,src,docs"
      ],
      "env": {
        "PROJECT_ID": "quote-system-x",
        "LOG_LEVEL": "info",
        "AWS_ACCESS_KEY_ID": "...",
        "AWS_SECRET_ACCESS_KEY": "...",
        "AWS_REGION": "us-east-1"
      }
    }
  }
}
```

## 🏗 Architecture

The server is designed as a **Stateful Control Plane** with a decoupled, domain-driven architecture:

1. **Dispatcher (`workers.go`)**: A managed worker pool that handles long-running operations. It ensures concurrency control and provides "Self-Healing" capabilities by resuming interrupted jobs from the database.
2. **Indexer (`indexer.go`)**: Integrates SQLite **FTS5** for instant, high-performance searching across project documentation and logs. It monitors files via `fsnotify` for real-time updates.
3. **Persistence Layer (`db_*.go`)**: A modular set of database interfaces:
   - **Governance**: Council proposals, voting, and audit trails.
   - **Security**: RBAC permission management and encrypted secret storage.
   - **Observability**: Detailed telemetry and performance metrics.
4. **Middleware (`withRBAC`)**: A centralized security gate that intercepts every tool call to enforce the Role-Based Access Control policy and record execution time.
5. **Transport Layer**: Supports dual-mode communication:
   - **STDIO**: Optimized for local agent integration.
   - **SSE (HTTP)**: Supports real-time event streaming and remote monitoring.
6. **Background Maintenance**: A dedicated loop handles data retention policies and system health checks.

---
*Built with ❤️ by the Google Deepmind team for Advanced Agentic Coding.*
