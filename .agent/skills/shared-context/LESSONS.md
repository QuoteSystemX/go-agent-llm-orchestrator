# Shared Context Lessons 🧠

### [2026-04-28] [CORE] [shared-context] Initial Knowledge Setup

- **Context**: Project initialization.
- **Root Cause**: Need for a persistent experience base.
- **Prevention**: Use this file to store insights from all agents.

### [2026-05-02] [INFRA] [shared-context] tasks/ directory must always exist

- **Context**: Multiple agents (task_miner, orchestrator) assume `tasks/` exists and write to it without checking.
- **Root Cause**: The directory was never committed (only `.gitkeep` files were ignored).
- **Prevention**: Keep `tasks/.gitkeep` committed so the directory is always present after checkout.

### [2026-05-08] [INFRA] [shared-context] .agent/bus/ directory must be initialized

- **Context**: The context bus directory was missing, causing health check failures and preventing data sharing between agents.
- **Root Cause**: The directory was likely removed or not created during a reset, and `bus_manager.py` did not automatically initialize it on every run.
- **Prevention**: Use `python3 .agent/scripts/context/bus_manager.py clear` to ensure the directory and `context.json` are initialized if missing.

### [2026-05-19] [PATTERN] [shared-context] Zero-Polling Event-Driven State Machine via Go MCP and fsnotify

- **Context**: Coordinating multi-agent refactoring sessions and self-healing pipelines across stateless LLM turns.
- **Root Cause**: Traditional Python/Bash loop-based polling (`while sleep(1)`) wastes CPU idle cycles and context-switching, while in-memory state machines fail to persist state across agent rate-limits and process crashes.
- **Prevention**: Leverage a hybrid pattern: use simple JSON DTOs on disk (`.agent/bus/session_refactor.json`) as the Data Plane, and watch it in a background Go goroutine using `fsnotify` OS kernel events inside the `local-skill-server` MCP binary (Control Plane). This delivers sub-5ms reactiveness at exactly 0.0% CPU overhead under idle state.
