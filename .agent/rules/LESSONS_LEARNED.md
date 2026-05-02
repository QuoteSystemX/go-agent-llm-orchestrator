# Lessons Learned & Experience Base 🧠

This document contains "hard-won" technical insights and project-specific gotchas.

> **Mandatory Rule**: Every agent MUST read this file before starting a task.
> **Retention Policy**: Lessons older than 30 days are automatically moved to `wiki/archive/experience/` by `experience_distiller.py`.

---

## 🏛 Active Lessons

### [2026-04-28] [CORE] [shared-context] Initial Knowledge Setup

- **Context**: Project initialization.
- **Root Cause**: Need for a persistent experience base.
- **Prevention**: Use this file to store insights from all agents.

### [2026-04-28] [WATCHDOG] [telemetry] Guardrail Configuration

- **Context**: Setting up safety limits.
- **Root Cause**: Potential for token overruns in recursive subagent calls.
- **Prevention**: Always run `guardrail_monitor.py` before delegating complex work.

### [2026-05-02] [INFRA] [deployment-procedures] autonomous_reviewer_cron.py was missing

- **Context**: `self-driving-ops.yml` was calling a script that did not exist, causing daily CI failures.
- **Root Cause**: Script was referenced in GitHub Actions but never implemented.
- **Prevention**: When adding a new `.yml` workflow step, always create the corresponding script in the same commit.

### [2026-05-02] [INFRA] [shared-context] tasks/ directory must always exist

- **Context**: Multiple agents (task_miner, orchestrator) assume `tasks/` exists and write to it without checking.
- **Root Cause**: The directory was never committed (only `.gitkeep` files were ignored).
- **Prevention**: Keep `tasks/.gitkeep` committed so the directory is always present after checkout.

---

## How to add a lesson:
Format: `### [YYYY-MM-DD] [TAG] [skill-name] Short Title`
Follow with Context, Root Cause, and Prevention bullets.

Skill tags must match skill folder names (e.g., `go-patterns`, `telemetry`, `shared-context`).
Use `python3 .agent/scripts/experience_distiller.py --list-skills` to see all active tags.
