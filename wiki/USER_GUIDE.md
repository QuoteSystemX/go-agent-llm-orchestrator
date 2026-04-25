# 📖 Jules Orchestrator: User Guide (Pro Max)

Welcome to the autonomous orchestration engine. This guide covers how to manage and monitor your agentic workflows using the premium Management Dashboard.

## 🖥️ Using the Dashboard

The dashboard is accessible at `http://jules.lab.me/dashboard`.

### 📋 Managing Tasks

- **Jules Badge**: A separate blue badge (e.g., `5 Jules`) indicates active Jules sessions for a repository. Clicking it (planned) will show detailed session status.
- **Create New Task**: Click the "+ New Task" button. Key fields:
  - **Mission**: The LLM prompt.
  - **Agent**: The AI persona (e.g., `backend-specialist`).
  - **Pattern**: Workflow strategy (e.g., `discovery`, `full_cycle`).
  - **Importance (1-10)**: Priority weighting.
  - **Category**: `worker` (general) vs `service` (maintenance).
  - **Require Plan Approval (HITL)**: If enabled, the agent will pause after planning and wait for your manual approval.

### 🔍 Viewing Execution Logs

Click the **"Logs"** button on any task card to open the history.

- **Payload Audit**: See exactly what was sent to Jules (**IN**) and what Jules responded (**OUT**).
- **Phase Breakdown**: Complex tasks show individual phases (Analysis, Planning, etc.) with timing.
- **Status tracking**: Monitor real-time status updates from Jules.

## 🤖 LLM Configuration & Supervision

The orchestrator uses LLMs for three primary functions:

### 1. Hybrid Routing

Based on the `mission` complexity, the orchestrator determines whether to use a fast local model or a high-reasoning cloud model.

- **Local Model**: Used for `SIMPLE` tasks and DTO. Configure via **Settings > Local LLM**.
- **Remote Model**: Used for `COMPLEX` tasks. Configure via **Settings > Remote LLM**.

### 2. Task Execution

The `mission` field in your task configuration is the core prompt.

### 3. Supervision (Auto-Responder)

If an agent becomes blocked (status: `AWAITING_USER_FEEDBACK`), the orchestrator:

1. Analyzes the session context using RAG.
2. Generates a logical response to Jules's question.
3. Resumes the session autonomously.

Configure trigger statuses in **Settings > Supervisor Triggers**.

## ⚙️ Configuration via Web UI

Click the **"Settings"** button to adjust:

1. **Telegram**: Bot token for execution notifications.
2. **Local/Remote LLM**: Model names, endpoints, and API keys.
3. **Jules API**: Credentials and base URL for Google Jules.
4. **Supervisor Triggers**: Select which Jules statuses should trigger the auto-responder.
5. **Prompt Library (Git)**: Configure where to sync agent templates and workflows from.
6. **Log Retention**: Set how many days to keep execution history (default: 7).
7. **Global Quota**: Set daily task limits to control LLM costs.

## 🛠️ Maintenance

### Database Persistence

The state is stored in SQLite databases inside the mounted K8s Persistent Volume.

- **Path**: `/app/data/tasks.db` (Config) and `/app/data/history.db` (Logs).

### Manual Troubleshooting

If the dashboard is unreachable, check the pod logs:

```bash
kubectl logs -l app=jules-orchestrator
```

---
> Part of the **Antigravity Kit** for automated agentic coding.
