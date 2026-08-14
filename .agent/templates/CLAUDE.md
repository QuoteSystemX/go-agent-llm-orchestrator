# CLAUDE.md

> This file is auto-provisioned by the Antigravity Kit from `prompt-library`, **once, on first
> deploy only** — `distribute-agentic-kit.yml` copies it here only if this repo has no
> `CLAUDE.md` yet. After that, this repo owns and maintains its own copy: editing
> `.agent/templates/CLAUDE.md` in `prompt-library` and pushing to main will **not** update this
> file again, in this repo or any other already-provisioned one — it only affects repos added to
> `.github/distribution.yml` for the first time afterward.
>
> Content that must reach every repo automatically and unattended — including this one, on every
> kit sync — belongs in `.agent/ARCHITECTURE.md` instead (synced weekly and on every push to
> `main` touching `.agent/**`), not here. That's why the "Architecture Reference" section below
> `@`-includes it: edit there, not here, for anything meant to be kit-wide and self-updating.

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
