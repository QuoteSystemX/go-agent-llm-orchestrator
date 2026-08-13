---
name: harness-development
description: How to add a new harness (LLM CLI) to the capability-driven harness_run system. Covers manifest schema (harnesses.yaml), capability matrix updates, security review, and validation. Use when adding a new LLM CLI (claude, codex, gpt-cli, etc.), updating an existing harness, or when asked to "add a new model" or "register a new tool".
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
version: 1.0.0
files: capability-mapping.md, examples.md, manifest-schema.md, scripts/harness_validate.py, security-review.md
---

# Harness Development

> How to add, modify, and validate harnesses (LLM CLI tools) in the
> capability-driven `harness_run` system introduced in STORY-5.
> **Read this BEFORE editing `harnesses.yaml` or adding a new model.**

## 🎯 When to Use This Skill

- Adding a new LLM CLI (e.g., `codex`, `gigachat-cli`, `gpt-cli`)
- Updating an existing harness's manifest (timeout, args, env)
- Debugging a `CAPABILITY_DENIED` error from `bin/harness_run`
- Performing a security review of a harness manifest
- Validating that all manifests pass the schema check

## 📑 Content Map

| File | Description | When to Read |
|------|-------------|--------------|
| `manifest-schema.md` | The YAML schema for each entry in `harnesses.yaml` | First-time harness creation |
| `capability-mapping.md` | How to wire harness capabilities to the matrix | Adding/modifying a harness |
| `security-review.md` | Pre-merge checklist + threat model | Before adding a new harness |
| `examples.md` | Worked examples: adding codex, adding a custom tool | Reference |

---

## 🚦 Quick Decision Tree

```
Want to add a new LLM CLI?
│
├─ Is the CLI a fork of claude/codex/etc?
│  └─ YES → Copy the existing claude entry, change binary + name
│
├─ Is it a brand new tool (e.g., a local LLM runner)?
│  └─ Follow manifest-schema.md + capability-mapping.md
│
└─ Want to update an existing harness?
   └─ Edit the entry, run `bin/harness_run --validate`
```

## 🚨 RED FLAGS (Stop and Ask)

Before adding a new harness, STOP if:
- The CLI is `shell=True` (NEVER use shell, list args only)
- The CLI requires `LD_PRELOAD` or other dangerous env vars
- The CLI needs network access (manifest has `network: deny` by default)
- The CLI is not in your PATH and not in repo
- You cannot find its `--help` output to verify args

If any of the above, escalate to `@security-auditor` before proceeding.

## 📋 Quick Reference

```bash
# Validate all manifests
bin/harness_run --validate

# List registered harnesses
bin/harness_run --list

# Show one manifest
bin/harness_run --manifest claude

# Run a harness (requires capability)
bin/harness_run --harness claude --prompt-file ./task.md --caller-role infra-agent

# Run pre-deploy audit (validates capabilities matrix)
python3 .agent/scripts/dev/capability_audit.py
```

## 📚 Key References

- `.agent/HARNESS_CONTRACT.md` — full spec (read this first)
- `wiki/decisions/ADR-008-harness-run-v2-capability.md` — decision record
- `.agent/config/harnesses.yaml` — current manifests
- `.agent/config/capabilities.yaml` — capability matrix
- `bin/harness_run` — runtime
- `.agent/skills/harness-development/scripts/harness_validate.py` — validation script

