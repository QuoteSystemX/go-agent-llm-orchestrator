# 📖 Jules Orchestrator: User Guide (Pro Max)

Welcome to the autonomous orchestration engine. This guide covers how to manage and monitor your agentic workflows using the premium Management Dashboard.

## 🖥️ Using the Dashboard

The dashboard is accessible at `http://jules.lab.me/dashboard`.

### 📋 Managing Tasks

- **Create New Task**: Click the "+ New Task" button in the header. You can specify the task name, **mission** (this is the LLM prompt sent to the agent), pattern, and cron schedule.
- **Edit Task**: Click the "Edit" button on any task card. Changes to the schedule or mission are applied instantly without service restarts.
- **Pause/Resume**: Use the Play/Pause buttons to toggle task execution. Paused tasks will not be triggered by the cron engine.
- **Delete**: Remove a task from the system. (Note: Logs for deleted tasks are also removed via cascade).

### 🔍 Viewing Execution Logs

Click the **"Logs"** button on any task card to open the Execution History viewer.

- **Payload Audit**: You can see exactly what was sent to the agent (**IN**) and what the agent responded (**OUT**). This allows you to audit the LLM's reasoning and responses.
- **Status & Timing**: Every run displays its success/failure status and the total duration in milliseconds.
- **Error Tracking**: If a task fails, the specific error message will be displayed in the log entry.

## 🤖 LLM Configuration & Supervision

The orchestrator uses LLMs for three primary functions:

### 1. Hybrid Routing
Based on the `mission` complexity, the orchestrator determines whether to use a fast local model or a high-reasoning cloud model.
- **Local Model**: Used for `SIMPLE` tasks. Configure via `LLM_LOCAL_ENDPOINT` and `LLM_LOCAL_MODEL`.
- **Remote Model**: Used for `COMPLEX` tasks (e.g., Claude 3.5). Configure via `LLM_REMOTE_ENDPOINT` and `LLM_REMOTE_API_KEY`.

### 2. Task Execution
The `mission` field in your task configuration is the core prompt. The orchestrator passes this to the selected agent session. The quality of the response depends on the model selected during routing.

### 3. Supervision (Auto-Responder)
If an agent becomes blocked (status: `WAITING_FOR_USER`), the orchestrator automatically:
1. Analyzes the session context using the local LLM.
2. Generates a logical response to the agent's question.
3. Resumes the session autonomously.
You can monitor these events in the Pod logs or by checking the `task_logs` for "Auto-responded" patterns.

## ⚙️ Configuration via Web UI

You can adjust certain system settings without re-deploying:

1. Click the **"Settings"** button in the header.
2. **Telegram**: Provide your bot token to receive execution notifications.
3. **Local LLM**: Change the model name (e.g., `phi3:mini`, `llama3`) used for local tasks and classification.
4. Click **"Save Changes"** to apply instantly.

## ⚙️ Helm Integration

While you can manage tasks via UI, the "Source of Truth" for defaults is managed in the `RecipientOFQuotes-Charts` repository.

### Updating Defaults

1.  Edit `values.yaml` in the `go-agent-llm-orchestrator` chart.
2.  Update the `distribution` section with your tasks.
3.  Deploy via `helm upgrade`.
4.  The orchestrator will automatically sync these defaults into SQLite on the next boot.

## 🛠️ Maintenance

### Database Persistence

The state is stored in `tasks.db` inside the mounted K8s Persistent Volume.

- **Storage Path**: `/app/data/tasks.db`
- **Schema**: Includes `tasks` and `task_logs` tables.

### Manual Troubleshooting

If the dashboard is unreachable, check the pod logs:

```bash
kubectl logs -l app=jules-orchestrator
```

---
> Part of the **Antigravity Kit** for automated agentic coding.
