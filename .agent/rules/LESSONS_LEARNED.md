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

---

## How to add a lesson:
Format: `### [YYYY-MM-DD] [TAG] [skill-name] Short Title`
Follow with Context, Root Cause, and Prevention bullets.

Skill tags must match skill folder names (e.g., `go-patterns`, `telemetry`, `shared-context`).
Use `python3 .agent/scripts/experience_distiller.py --list-skills` to see all active tags.

### [2026-01-01] [INFO] [test] The magic word is xyzzy

### [2026-05-01] [INFO] [regression] Regression secret word: quack

### [2026-05-01] [INFO] [regression] Regression secret word: quack

### [2026-05-01] [INFO] [regression] Regression secret word: quack

### [2026-05-01] [INFO] [regression] Regression secret word: quack

### [2026-05-01] [INFO] [regression] Regression secret word: quack

### [2026-05-01] [INFO] [regression] Regression secret word: quack

### [2026-05-01] [INFO] [regression] Regression secret word: quack

### [2026-05-01] [INFO] [regression] Regression secret word: quack

### [2026-05-01] [INFO] [regression] Regression secret word: quack

### [2026-05-01] [INFO] [regression] Regression secret word: quack

### [2026-05-01] [INFO] [regression] Regression secret word: quack

### [2026-05-01] [INFO] [regression] Regression secret word: quack

### [2026-05-01] [INFO] [regression] Regression secret word: quack

### [2026-05-01] [INFO] [regression] Regression secret word: quack

### [2026-05-01] [INFO] [regression] Regression secret word: quack

### [2026-05-01] [INFO] [regression] Regression secret word: quack

### [2026-05-01] [INFO] [regression] Regression secret word: quack

### [2026-05-01] [INFO] [regression] Regression secret word: quack

### [2026-05-01] [INFO] [regression] Regression secret word: quack

### [2026-05-01] [INFO] [regression] Regression secret word: quack

### [2026-05-01] [INFO] [regression] Regression secret word: quack
