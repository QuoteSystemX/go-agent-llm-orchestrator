# 🚀 Jules Orchestrator (Pro Max Ultra)

Autonomous, RAG-enhanced agentic platform for the Antigravity Kit. Orchestrates LLM agents across repository fleets with deep integration into **Google Jules**.

## 📋 Overview

Jules Orchestrator manages the lifecycle of AI agents working on your codebases. It implements the **BMAD (Discovery-Planning-Execution-Verification)** methodology, ensuring that every change is reasoned, planned, and validated.

### Key Features

- **Google Jules Integration**: Native support for Jules sessions with Source Context API for deep repository understanding.
- **Autopilot Engine**: Dynamic scaling of workers based on repository task backlogs.
- **Autonomous Supervision**: Intelligent unblocking of sessions using automated supervisor responses.
- **Source-Aware RAG (DTO)**: Automated repository indexing and code search using embeddings.
- **Priority Traffic Manager**: Intelligent queuing of LLM requests to manage rate limits and local resources.
- **Git-Based Prompt Library**: Centralized management of agent templates and workflows.
- **Real-time Dashboard**: Full-stack Web UI for monitoring tasks, logs, and system health.

## 🛠️ Architecture

The system consists of several internal engines working in concert:

- **Scheduler**: Cron-based task triggering.
- **Autopilot**: Resource management.
- **DTO**: Repository analysis.
- **Supervisor**: Session management.

See [Architecture Guide](wiki/ARCHITECTURE.md) for details.

## 🚀 Quick Start

### Prerequisites
- **Go 1.26+**
- **Ollama** (for local tasks)
- **SQLite 3**
- **Google Jules API Key**

### Installation & Run

```bash
# Build the orchestrator
go build -o orchestrator ./cmd/orchestrator/main.go

# Start the service
./orchestrator
```

## ⚙️ Configuration

The orchestrator is configured via Environment Variables and a `distribution.yml` file.

| Variable | Description |
| :--- | :--- |
| `JULES_API_KEY` | API Key for Google Jules (**Required**) |
| `JULES_API_URL` | Jules API Base URL |
| `LLM_LOCAL_ENDPOINT` | Ollama URL (default: <http://localhost:11434>) |
| `DB_PATH` | Path to SQLite DB |
| `DISTRIBUTION_CONFIG_PATH`| Path to distribution YAML |

See [User Guide](wiki/USER_GUIDE.md) for the full list of settings.

## 📚 Documentation
- [Architecture Overview](wiki/ARCHITECTURE.md)
- [User Guide & Configuration](wiki/USER_GUIDE.md)
- [PRD (Requirements)](wiki/PRD.md)

---
> Part of the **Antigravity Kit** for automated agentic coding.
