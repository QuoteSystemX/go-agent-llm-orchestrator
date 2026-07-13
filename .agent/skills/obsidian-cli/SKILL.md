---
name: obsidian-cli
description: Interact with Obsidian vaults using the Obsidian CLI — read, search, and manage notes. Also supports plugin and theme development. Use when the user asks to interact with their Obsidian vault from the command line, or when working with Obsidian plugins.
version: 1.0.0
scope_restriction: manual_only
---

# Obsidian CLI Skill

Use the `obsidian` CLI to interact with a running Obsidian instance. Requires Obsidian to be open.

> ⚠️ **Read-only policy**: Only read/search commands are allowed. Never use destructive commands (delete, overwrite) without explicit user confirmation.

## Command reference

Run `obsidian help` to see all available commands.

## Read Operations

```bash
obsidian read file="My Note"
obsidian search query="search term" limit=10
obsidian backlinks file="My Note"
obsidian tags sort=count counts
obsidian tasks daily todo
```

## Create Operations (with confirmation)

```bash
obsidian create name="New Note" content="# Hello" template="Template" silent
obsidian append file="My Note" content="New line"
obsidian property:set name="status" value="done" file="My Note"
```

## Daily Notes

```bash
obsidian daily:read
obsidian daily:append content="- [ ] New task"
```

## Plugin Development

After making code changes to a plugin or theme:

```bash
obsidian plugin:reload id=my-plugin
obsidian dev:errors
obsidian dev:screenshot path=screenshot.png
obsidian dev:console level=error
```

## Syntax

**Parameters** take a value with `=`. Quote values with spaces:

```bash
obsidian create name="My Note" content="Hello world"
```

**Flags** are boolean switches with no value:

```bash
obsidian create name="My Note" silent overwrite
```

## Vault Targeting

Commands target the most recently focused vault by default:

```bash
obsidian vault="My Vault" search query="test"
```

## When to Use

- **Working with the Obsidian vault from the command line** —
  use `obsidian-cli` for automation, batch operations, CI.
- **Migrating content** — use `obsidian-cli convert` to translate
  between formats.
- **Bulk operations** — use `obsidian-cli tag`, `obsidian-cli move`,
  `obsidian-cli rename` for batch edits.
- **Vault validation** — combine with `@obsidian-validator` to
  check OFM compliance.

Avoid using this skill for:
- Reading/writing vaults from Python (use `obsidian-python-api`).
- UI interactions (use the Obsidian app directly).
- Cross-platform syncing (use Obsidian Sync).

## Anti-Patterns

- **Don't use `obsidian-cli` for one-off edits** — use the
  Obsidian app for occasional edits; CLI is for automation.
- **Don't run bulk operations without a backup** — always
  snapshot the vault before batch moves/renames.
- **Don't use `obsidian-cli convert` for partial migrations** —
  it converts the whole file, not portions.
- **Don't pipe `obsidian-cli` output through `grep | head`** —
  use the tool's built-in filter/limit flags for predictable
  output.
- **Don't run `obsidian-cli` in a directory that's not a vault**
  — it needs the `.obsidian/` config to work.
- **Don't skip dry-run** — most bulk operations have a `--dry-run`
  flag. Use it.

## Changelog

- **1.0.0** (2026-05-22): Initial version
