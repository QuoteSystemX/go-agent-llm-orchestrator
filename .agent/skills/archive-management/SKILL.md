---
name: archive-management
description: Manage long-term storage, archival of stale context, and history pruning policies.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
version: 1.0.0
---

# Archive Management Skill

> Maintain structural health of the repository logs and history by pruning stale entries and archiving legacy contexts.

## 🎯 When to Use This Skill

- **Trigger**: Retiring stale lessons from `.agent/rules/LESSONS_LEARNED.md` with expired TTL or `applied_count = 0`.
- **Trigger**: Moving legacy codebase configuration files to the `/archive` directory.
- **Trigger**: Auditing logs and artifacts size in `.agent/logs/` or `.agent/brain/`. Both are gitignored, runtime-created directories — they may not exist yet on a fresh checkout until something has logged to them.
- **Trigger**: Managing persistence policies for session snapshots.

---

## 📋 Archive Management Guidelines & Rules

### 1. Pruning Policy

Check for stale or expired items in `.agent/rules/LESSONS_LEARNED.md` periodically:
- **Rule 1**: If an entry has a TTL that is expired and has not been utilized (`applied_count = 0`), it **must** be pruned.
- **Rule 2**: Log the pruning action in `.agent/logs/archive.log` with the timestamp and author.
- **Rule 3**: Never delete lessons that are actively used (`applied_count > 0`).

### 2. Context Archiving Rules

- **Rule 4**: When archiving agent files or workflows, move them to the respective subfolder under `.agent/skills/archive/` or similar.
- **Rule 5**: Update references in `ARCHITECTURE.md` to prevent document drift after any file is moved to the archive.

---

## 💻 Code Examples & Archiving Patterns

### Archival Decision Table

| File Path | Criteria | Action | Target Location |
|---|---|---|---|
| `skills/old-plugin/` | Unused for 30+ days | Archive | `skills/archive/old-plugin/` |
| `logs/session_123.log` | Older than 7 days | Prune / Delete | None (Cleaned up) |
| `wiki/decisions/adr-001.md` | Replaced by new ADR | Update status | Keep in `wiki/decisions/` |

### Log Pruning Script Pattern

```bash
# Delete session logs older than 14 days
# mkdir -p first: .agent/logs/ is gitignored and runtime-created, so it may
# not exist yet on a fresh checkout — a bare `find` on a missing dir exits non-zero.
mkdir -p .agent/logs && find .agent/logs/ -name "*.log" -type f -mtime +14 -delete
```

---

## ❌ Anti-Patterns & Pitfalls to Avoid

- **Anti-Pattern (Blind Deletion)**: Avoid deleting logs or database states without making a backup or checking active sessions.
- **Anti-Pattern (Stale References)**: Don't move a skill folder to `archive/` without updating `skills-lock.json` and agent markdown files.
- **Anti-Pattern (Log Flooding)**: Avoid letting log files grow infinitely without rotation. This consumes disk space and degrades performance.
- **Anti-Pattern (Archiving Active Logic)**: Never archive a component that is still referenced in the CI/CD pipeline or active scripts.
