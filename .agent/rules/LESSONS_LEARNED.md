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

### [2026-05-03] [DOCS] [drift-detector] drift_detector.py must scan SKILL.md files

- **Context**: `drift_detector.py` was flagging documentation drift for scripts correctly documented in skill-specific `SKILL.md` files because it only scanned `ARCHITECTURE.md` and `wiki/`.
- **Root Cause**: The detector's search space was too narrow, ignoring the primary documentation source for individual skills.
- **Prevention**: Updated `drift_detector.py` to recursively include all `SKILL.md` files in `.agent/skills/` during the documentation sync check.

### [2026-05-06] [DOCS] [drift-detector] Expanded scan to .agent/.shared/

- **Context**: Documentation drift in shared UI components (`ui-ux-pro-max`) was not being detected correctly.
- **Root Cause**: `drift_detector.py` search path was hardcoded to `.agent/skills/`, missing components in `.agent/.shared/`.
- **Prevention**: Updated `drift_detector.py` to scan both `skills/` and `.shared/` directories for `SKILL.md` files. Created missing `SKILL.md` for shared components.

---

## How to add a lesson:
Format: `### [YYYY-MM-DD] [TAG] [skill-name] Short Title`
Follow with Context, Root Cause, and Prevention bullets.

Skill tags must match skill folder names (e.g., `go-patterns`, `telemetry`, `shared-context`).
Use `python3 .agent/scripts/experience_distiller.py --list-skills` to see all active tags.
