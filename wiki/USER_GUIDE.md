# 📖 Jules Orchestrator: User Guide

Welcome to the autonomous orchestration engine. This guide covers how to manage and monitor your agentic workflows.

## 🖥️ Using the Dashboard

The dashboard is accessible at `http://<ingress-host>/dashboard`.

### Key Sections:
- **Active Tasks**: Real-time view of all tasks defined in your configuration.
- **Status Indicators**:
    - 🟢 `RUNNING`: Task is currently executing a Jules session.
    - 🟡 `PAUSED`: Task is disabled and will not trigger on schedule.
    - ⚪ `PENDING`: Task is waiting for its next scheduled run.
- **Audit Logs**: A chronological record of "Supervision" events. When the Orchestrator's LLM intervenes to unblock an agent, it's logged here.

## ⚙️ Task Configuration (`distribution.yml`)

The orchestrator reads tasks from a YAML file. Use `distribution.example.yml` as a template.

### Fields:
- `name`: Full GitHub repository path (e.g., `owner/repo`).
- `agent`: The specialist agent to invoke (e.g., `analyst`, `debugger`, `orchestrator`).
- `pattern`: The workflow pattern to use.
- `mission`: The command or description of the task.
- `schedule`: Standard Cron expression.

## 🤖 Agent Supervision

The "Auto-Responder" logic automatically monitors sessions in the `WAITING_FOR_USER` state.
1. **Detection**: The Monitor detects a blocked session.
2. **Analysis**: The LLM Router reads the last few messages from the session.
3. **Decision**: If it's a routine architectural or implementation decision, the Supervisor posts a response.
4. **Resumption**: The agent receives the response and continues the mission.

## 📊 Monitoring

Metrics are exported for Prometheus at `/metrics`. You can track:
- `jules_sessions_triggered_total`: Total runs.
- `jules_api_errors_total`: API failures by endpoint.

## 🛠️ Maintenance

### SQLite Database
The state is stored in `tasks.db` inside the PVC.
- To view logs manually: `sqlite3 tasks.db "SELECT * FROM audit_logs;"`
- To reset state: Simply delete the database file (Kubernetes will recreate it).
