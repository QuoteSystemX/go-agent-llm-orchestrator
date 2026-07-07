---
name: multica-mcp
description: "Global Model Context Protocol (MCP) skills for Multica Core Platform (Issues/Tasks) and Lean-Ctx (Token/Context optimization)."
version: 1.0.0
---

# Multica Global MCP Skill

This skill documents and guides agents on utilizing global Model Context Protocol (MCP) servers available in the Multica Kubernetes cluster:
1. **Core Platform (`multica` and `agent-kit`)**: Issue and task management tools, logging progress, and task lifecycle operations.
2. **Context Manager (`lean-ctx`)**: Real-time token budget monitoring, request compression, and context reduction.

---

## 🛠️ CORE PLATFORM (ISSUES & TASKS)

The `multica` and `agent-kit` MCP servers provide tools to coordinate agent tasks and track issue tickets.

### When to use
- To log the start/end of a sub-task.
- To create, update, or query issue status in the workspace tracking system.
- To sync task progress with the platform.

### Standard Operations
- Use the issue management tools when creating sub-tasks for parallel execution.
- Ensure task descriptions are concise and well-structured.

---

## 🗜️ LEAN-CTX (TOKEN & CONTEXT OPTIMIZATION)

The `lean-ctx` MCP server provides 14 tools to monitor context windows and compress payloads.

### When to use
- When the context budget is high or approaching workspace limits.
- Before reading large files or grep outputs (use lean-ctx search or compression tools).
- To measure current request token usage.

### Best Practices
- **Compress outputs**: If a tool output exceeds 200 tokens, use `lean-ctx` compression.
- **Filter aggressively**: Prefer semantic search/filtering tools over dumping raw files to context.
