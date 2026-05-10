---
trigger: paperclip_infra_only
scope: "active on: paperclip paths, agentic orchestration tasks, or explicit agentic keywords"
---

## TIER 3: PAPERCLIP AGENTIC PROTOCOLS

### 📎 Paperclip Heartbeat Protocol (MANDATORY)

Every session with ANY agent MUST follow the Paperclip Heartbeat cycle (Skill: @[skills/paperclip]):

1. **Awareness**: Sync with current task and read `.agent/bus/` for context.
2. **Lenses**: Apply Domain Lenses based on role category (Management, Engineering, QA, Infra).
3. **Action**: Do not stop at planning; perform actionable work in the same heartbeat.
4. **Reporting**: Every session MUST end with a **Progress Report** (Status, Blockers, Next Action).
5. **Durable State**: Update task metadata and create child issues for delegated work.

### 🚀 High-Agency Completion

Agents in this workspace operate under the **"End-to-End"** principle.

1. **Never stop at planning**: If the path is clear, proceed to implementation in the same response.
2. **Hygiene is Mandatory**: Every code change must include necessary imports, basic error handling, and lint fixes.
3. **Self-Correction**: If a tool fails, analyze the error and attempt a fix or alternative path immediately without asking for permission for trivial adjustments.

### 📎 Paperclip Paradigm Alignment

All development must respect the Paperclip Core Architecture:

1. **Infrastructure First**: Prefer dynamic discovery (FS/API) over hardcoded registries in databases.
2. **MCP Integration**: New functionality should ideally be exposed via MCP tools to ensure cross-agent accessibility.
3. **Workspace Integrity**: Respect the `/paperclip` hierarchy and the separation of instances/workspaces.

### 🎯 Mission Awareness

We are building the future of agentic orchestration.

- **Goal**: Create a robust, premium, and autonomous ecosystem.
- **Standard**: "Minimum Viable Product" is not enough. Aim for "Production Ready" and "Feature Complete".
