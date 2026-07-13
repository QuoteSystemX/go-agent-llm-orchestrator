---
name: inbox-patterns
description: How to use the structured INBOX.md channel for human-to-agent communication. Covers intents (redirect, clarify, abort, context, ack), knowledge anchors, sanitization, and ack workflow. Use when sending messages to the running agent, when investigating agent behavior, or when designing a new INBOX-related feature.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
version: 1.0.0
---

# INBOX Patterns

> The INBOX channel at `tasks/INBOX.md` (JSONL) is the structured way
> for humans to communicate with running agents. This skill covers
> when to use each intent, how to anchor to KNOWLEDGE.md, and how the
> sanitization works.
> **Read this BEFORE sending your first INBOX message.**

## 🎯 When to Use This Skill

- Sending a message to a running agent (use the right intent!)
- Designing a new INBOX feature
- Investigating why an agent didn't see an INBOX message
- Writing an `ack` for a previous message
- Understanding why INBOX messages are sanitized

## 📑 Content Map

| File | Description | When to Read |
|------|-------------|--------------|
| `intents.md` | The 5 intents (redirect, clarify, abort, context, ack) — when to use each | Choosing the right intent |
| `knowledge-anchors.md` | How `redirect` and `context` reference KNOWLEDGE.md sections | Writing anchored messages |
| `sanitization.md` | Why and how INBOX bodies are sanitized before injection | Debugging missing/garbled content |
| `anti-patterns.md` | Common mistakes (markdown in body, missing anchor, etc.) | Reviewing INBOX messages |

---

## 🚨 RED FLAGS (Stop and Ask)

Before sending an INBOX message, STOP if:
- The body contains markdown (`*`, `_`, `>`), HTML (`<tag>`), or code (`code blocks`)
- The body is >2000 characters (truncation will silently lose info)
- You're about to use `intent: redirect` without `--anchor` (will be rejected)
- You want to "secretly inject instructions" (the schema validator catches prompt injection)

## 📋 Quick Reference

```bash
# Send a message
bin/inbox send <intent> <body> [--target AGENT] [--anchor SECTION] [--ack-required]

# List pending
bin/inbox list [--intent X] [--target Y]

# Ack a previous message
bin/inbox ack <entry_id>

# View the schema
bin/inbox schema

# View in browser (sandboxed HTML)
python3 -m http.server 8080 --directory tasks
# then open http://localhost:8080/INBOX_viewer.html
```

## 📚 Key References

- `.agent/config/inbox.schema.json` — the schema
- `.agent/scripts/communication/inbox.py` — API
- `.claude/commands/inbox.md` — slash command
- `bin/inbox` — CLI
- `tasks/INBOX_viewer.html` — sandboxed HTML viewer
- `.agent/agents/specialists/runtime/inbox-attendant.md` — agent persona
- `wiki/decisions/` — ADRs about INBOX design
- `.agent/skills/inbox-patterns/scripts/inbox_validate.py` — validation script

