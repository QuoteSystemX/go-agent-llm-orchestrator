# CLAUDE.md

> This file is auto-provisioned by the Antigravity Kit from `prompt-library`.
> To update: edit `.agent/templates/CLAUDE.md` in `prompt-library`, push to main.

## Technical Standards & Engineering Rules

@.agent/KNOWLEDGE.md

## Agent System

Agents for Claude Code live in `.claude/agents/` (auto-generated from `.agent/agents/`).
Agents for Antigravity (Gemini) live in `.agent/agents/`.

Do not edit `.claude/agents/` directly — they are regenerated on each kit sync.

## Architecture Reference

@.agent/ARCHITECTURE.md

## Task Queue

Active tasks are in `tasks/` at the repo root. Agents pick up tasks matching their domain tags.

See `.agent/KNOWLEDGE.md` → "Task Management" section for routing matrix and conventions.
