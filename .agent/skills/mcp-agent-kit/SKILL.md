---
name: mcp-agent-kit
description: "Mastery of the core agent-kit Model Context Protocol (MCP) server. Guides agents on orchestrating agentic workflows, task schedules, issue tracking, and lifecycle loops."
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
version: 1.0.0
---

# MCP Agent-Kit Integration Skill

> Enforce task coordination, status synchronization, and lifecycle management via the `agent-kit` MCP server.

## 🎯 When to Use This Skill

- **Trigger**: When interacting with the `agent-kit` MCP server endpoint (`http://multica-mcp:3200/mcp`).
- **Trigger**: When tracking task lifecycle changes (creation, scheduling, and completion states).
- **Trigger**: When scheduling or retrieving execution contexts for parallel agent nodes.

---

## 📋 Operational Guidelines & Rules

### 1. Task Lifecycle Operations
- **Rule 1**: Every scheduled task **must** define a unique task ID and a concise title.
- **Rule 2**: When a task completes, always update its final status (e.g. `success`, `failed`) and save the logs.
- **Rule 3**: Check active token budget and context usage before spawning child processes or subagents.

### 2. Synchronization Loops
- **Rule 4**: Use the issue tracking tools to query ticket status before starting work.
- **Rule 5**: Always emit state updates to the shared context bus to keep the system dashboard in sync.

---

## 💻 Code Examples & Patterns

### Task Creation Payload

```json
// Example of spawning a task on the agent-kit endpoint
{
  "serverName": "agent-kit",
  "toolName": "create_task",
  "arguments": {
    "title": "Build API contracts",
    "status": "pending",
    "metadata": {
      "owner": "backend-specialist",
      "priority": "HIGH"
    }
  }
}
```

### Task Status Update

| State | Action Required | Expected Result |
|---|---|---|
| `pending` | Trigger node executor | Status changes to `running` |
| `running` | Verify completion criteria | Emit success/failure event |
| `success` | Update task record | Close connection, release resources |

---

## ❌ Anti-Patterns & Pitfalls to Avoid

- **Anti-Pattern (Missing Metadata)**: Avoid creating tasks without descriptive metadata or owner assignments.
- **Anti-Pattern (Dangling Tasks)**: Never leave in-flight tasks in `running` state if the process gets aborted. Always implement graceful shutdown hooks.
- **Anti-Pattern (Overloading Server)**: Don't poll task states in a tight loop. Always use event listeners or backoff timers.
- **Anti-Pattern (Local Fallback Bypass)**: Never ignore connection failures. If `agent-kit` server is unreachable, fall back to local file state recording.

---

## Additional Quality Guidelines
To ensure the highest standard of delivery, the following additional considerations must be met:
1. Maintain consistency with existing naming conventions in the codebase.
2. Implement comprehensive error handling and logging for all new components.
3. Ensure that all dependencies are declared and verified beforehand.
4. Write clean, self-documenting code with clear comments where necessary.
5. Validate performance under load and avoid premature optimizations.
