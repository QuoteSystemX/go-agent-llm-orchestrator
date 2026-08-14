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
- **Trigger**: `tasks/done/` has stray top-level cards, a stale/missing `INDEX.md`, or a cluster of
  near-identical cards that should be distilled and pruned. See "Task Archive Policy" in
  `.agent/ARCHITECTURE.md` for the mandatory rules; this skill covers the mechanics.

### `tasks/done/` maintenance

Run `python3 .agent/scripts/delivery/task_archive.py` to partition stray cards into
`tasks/done/YYYY-MM/` and regenerate `INDEX.md`. Use `--check` in CI/pre-commit contexts.

The `Distilled?` / `Wiki link` columns in `INDEX.md` are filled in **by hand**, not auto-detected
— an agent (or human) sets them only after actually writing the distillation. Auto-detecting via
a slug/keyword grep against `wiki/` risks false positives (a partial word match marking a card
"distilled" when nothing was actually written), which silently loses the "did we really capture
this" signal the column exists to provide. Trade-off: this means the column starts empty and only
fills in as agents do the work — a stale/empty `INDEX.md` reveals distillation backlog rather
than hiding it.

Wiki cross-linking rule: 3+ cards converging on the same architectural point (not just a shared
keyword) → write a `wiki/` page, backlink it from each card and its `INDEX.md` row, mark those
cards `Distilled? = yes`. Once a cluster is both distilled *and* genuinely redundant (e.g. an
auto-generated card repeating the identical root cause — see the Archival Decision Table below),
it's a prune candidate per Rule 1-3 above; a wide feature surface where each card documents a
*different* thing is not.

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
| `tasks/done/*.md` (single card) | Auto-partition + index | Keep, move | `tasks/done/YYYY-MM/`, row in `INDEX.md` |
| `tasks/done/*.md` (recurring cluster, same root cause, distilled into one lesson) | Redundant with the lesson | Prune / Delete | None — lesson lives in `LESSONS_LEARNED.md` / `wiki/` |
| `tasks/done/*.md` (unique investigation, even if large) | Never — value is in the reasoning | Keep, index only | `tasks/done/YYYY-MM/`, `Distilled?` = manual |

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
