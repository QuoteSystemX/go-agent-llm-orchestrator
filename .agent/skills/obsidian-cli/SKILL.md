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
