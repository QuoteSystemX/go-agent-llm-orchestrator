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
- **Jules Link**: Clicking the session ID in the task list now opens the native Jules UI at `jules.google.com`.
- **Paginated History**: Task logs now support infinite history via "Load More", enabling deep forensics for older sessions.

## 🛡️ Command Center & Transparency

The **Command Center** provides deep visibility into the orchestrator's autonomous operations via specialized tabs:

### 1. 🛡️ Audit Logs

Track every significant system action that happens behind the scenes.

- **Auto-Responses**: See when the Supervisor responded to a blocked session.
- **Routing Decisions**: Track when tasks are escalated to more powerful models.
- **Governance Events**: See when a budget limit was hit or adjusted.

### 2. 📋 Traffic Queue

Monitor real-time execution queuing.

- **Waiting Tasks**: View all tasks currently waiting for a free worker slot.
- **Wait Duration**: See exactly how long a task has been pending.
- **Bump Priority**: Manually prioritize a specific task to move it to the front of the queue.

### 3. 💰 Budgets & Governance

Enforce financial and operational safety limits.

- **System Quota**: Global daily session and monthly cost limits.
- **Project Budgets**: Specific limits for individual repositories to prevent "experiment" repos from consuming the main quota.
- **Alerts**: Configure thresholds (e.g., 80%) for Telegram notifications.

### 4. 🧭 Documentation Drift

Maintain a healthy relationship between code and documentation.

- **Drift Badges**: Repositories show **🍏 SYNCED** or **⚠️ DRIFT** badges.
- **Automated Check**: The system hashes `ARCHITECTURE.md` and core Wiki pages vs. the source code.
- **Resolution**: Use the `wiki-architect` agent to reconcile documentation if drift is detected.

## 🤖 Autopilot & Backlog Management

The orchestrator includes an **Autopilot Engine** that optimizes resource usage:

1. **Backlog Scanning**: Every 10 minutes, the engine scans the `tasks/` folder of each managed repository.
2. **Dynamic Scaling**: If `.md` or `.json` tasks are found, Autopilot activates the corresponding `worker` tasks (sets status to `PENDING`).
3. **Idle Pause**: When the backlog is empty, Autopilot pauses the workers to save costs and context.

## 🔍 DTO: Source Code Search & RAG

To provide agents with deep project context, the orchestrator implements **DTO (DAG-based Task Orchestration)**:

- **Automated Indexing**: Repositories are periodically synced and indexed into a local vector store.
- **Context Injection**: When a task starts, the orchestrator identifies relevant code chunks and provides them to the Jules session via the **Source Context API**.
- **Performance**: Indexing is limited to files < 100KB to ensure fast search and optimal LLM context usage.

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

- **Automation**: Combines with Helm to manage deployment in Kubernetes.

## 💾 System Backup & Restore

The orchestrator includes a built-in backup utility to protect your task configurations, history, repositories, and RAG indices.

### 1. Exporting System State

Go to **Settings > System Management** or use the direct endpoint:

- **Action**: Generates a password-protected ZIP archive (`.zip`).
- **Includes**:
  - `tasks.db` (Configurations)
  - `history.db` (Execution logs & Audit)
  - `repos/` (Managed repository clones)
  - `prompt-lib/` (Custom prompt templates)
  - `chromem_db/` (Vector embeddings & RAG index)

### 2. Importing System State

- **Safety**: The system will automatically pause execution engines before applying the import.
- **Verification**: Integrity and password verification are performed before overwriting any data.
- **Persistence**: Temporary snapshots are stored in the persistent `dataDir` to prevent memory overflow in large-scale environments.

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
