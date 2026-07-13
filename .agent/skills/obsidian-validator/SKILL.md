---
name: obsidian-validator
description: Validate, repair, and migrate Obsidian vault contents. Run checks on wikilinks, frontmatter, callouts, and orphans. Use when the vault needs integrity verification, after editing wiki files, or when setting up a new vault.
version: 1.0.0
scope_restriction: vault_path
---

# Obsidian Validator Skill

Validate and repair Obsidian vault contents. The validator ensures all wiki files are OFM-compliant and internally consistent.

## Usage

### Check vault health

```bash
python3 .agent/scripts/knowledge/obsidian_validator.py check
```

Options:
- `--fix` — auto-repair broken links and missing frontmatter
- `--json` — machine-readable JSON output
- `--path <dir>` — check a specific directory

### Get status report

```bash
python3 .agent/scripts/knowledge/obsidian_validator.py status
```

Shows:
- Vault location and file count
- OFM compliance percentage
- Detected documentation directories (docs/, guide/, etc.)
- Recommended actions

### Initialize new vault

```bash
python3 .agent/scripts/knowledge/obsidian_validator.py init [--path <dir>]
```

Creates:
- Vault directory with `.obsidian/` config
- `_index.md` as Map of Content

### Migrate existing files to OFM

```bash
python3 .agent/scripts/knowledge/obsidian_validator.py migrate [--dry-run] [--backup]
```

Converts files to OFM-compliant format with:
- Required frontmatter (title, tags, status)
- Fixed broken wikilinks (stub creation)
- Git backup branch (optional)

### Merge documentation into vault

```bash
python3 .agent/scripts/knowledge/obsidian_validator.py merge --from=docs [--dry-run]
```

Moves `.md` files from another directory into the vault.

## Automation

The validator runs automatically via:
- `output_bridge.py` — validates when generating session reports
- `checklist.py` — part of the knowledge coverage check
- Git hooks (future) — pre-commit validation

## What Gets Checked

| Check | Description |
|-------|-------------|
| Broken links | `[[wikilinks]]` pointing to non-existent files |
| Orphans | Files with no incoming links |
| Frontmatter | Missing required fields (title, tags, status) |
| Callouts | Invalid `> [!type]` syntax |
| Compliance | Overall OFM compatibility score |

## Changelog

- **1.0.0** (2026-05-22): Initial version

## When to Use

- **After editing wiki files** — run `obsidian_validator.py check` before
  committing to catch broken links and missing frontmatter.
- **Before merge to main** — add `make obsidian` (or
  `obsidian_validator.py check --json`) to pre-deploy checks.
- **Setting up a new vault** — use `init` to scaffold `.obsidian/`
  config and an `_index.md` Map of Content.
- **Migrating legacy docs** — use `migrate` to convert plain Markdown
  to OFM-compliant files (with `--dry-run` first).
- **Investigating obsidian errors** — use `status` to get a diagnostic
  report (vault location, file count, OFM %).

Avoid using this skill for:
- Validating non-Obsidian Markdown (e.g., GitHub README files).
- Real-time editing validation (this is a batch tool, not an LSP).
- Generating content (use `@wiki-architect` for that).

## Anti-Patterns

- **Don't ignore obsidian errors** — they indicate real broken links
  or missing frontmatter. Block the PR until fixed.
- **Don't use `--fix` blindly in production** — `--fix` modifies the
  vault in place. Run `--dry-run` first to preview changes.
- **Don't skip the `IGNORE_DIRS`** — they exist to keep runtime
  data (e.g., `bus/`, `data/`) out of the validation. If you
  remove them, the validator will flag artifacts.
- **Don't commit without running `check`** — the validator is the
  gatekeeper. A clean `check` is a prerequisite for `git push`.
- **Don't use `init` over an existing vault** — it will overwrite
  `.obsidian/` config. Backup first if you must.
- **Don't use the validator as a linter for prose** — it only
  checks structural integrity (links, frontmatter, callouts),
  not grammar or content quality.
