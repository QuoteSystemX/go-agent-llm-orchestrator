---
name: knowledge-injection
description: Register, re-inject, and validate distilled lessons into system context for future agent sessions.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
version: 1.0.0
---

# Knowledge Injection Skill

> Manage the re-application of distilled codebase wisdom and lessons learned into subsequent agent sessions.

> **Write side of the lessons pipeline.** This skill covers *registering* lessons (`knowledge_inject.py`:
> `register_lesson`, TTL, active flag). To *retrieve and inject* existing lessons at the start of a new
> task, see [experience-injector](../experience-injector/SKILL.md) instead.

## 🎯 When to Use This Skill

- **Trigger**: Injecting lessons learned from `.agent/rules/LESSONS_LEARNED.md` into active agent prompt contexts.
- **Trigger**: Running the `.agent/scripts/communication/knowledge_inject.py` script to update system prompt templates.
- **Trigger**: Resolving issues where distilled context is stale, corrupted, or failing to load dynamically.
- **Trigger**: Verifying that newly created files or logic conform to active project guidelines.

---

## 📋 Knowledge Injection Guidelines & Rules

### 1. Registration Loop

Every archivist agent **must** follow these rules:
- **Rule 1**: When a new lesson is saved, it **must** be written to `.agent/rules/LESSONS_LEARNED.md` using the standard format.
- **Rule 2**: Assign proper metadata to each lesson (creation timestamp, TTL, active flag, and count).

### 2. Injection Rules

- **Rule 3**: Before starting a new task/session, the system **should** read the registered active lessons.
- **Rule 4**: Injected lessons **must** be inserted dynamically into the LLM system prompt prefix (under the designated `History` section).
- **Rule 5**: Check that the injected lessons do not exceed the headroom or token limit constraints.

---

## 💻 Code Examples & Injection Patterns

### Lesson Registration Format

```markdown
### [LESSON-001] Avoid direct shell command execution

- **Context**: Executing git or build commands in shell wrappers.
- **Problem**: Host lacks locale settings or shell wrappers fail on quote characters.
- **Solution**: Always use executive arrays (e.g., `exec.Command("git", "log")`) instead of `exec.Command("bash", "-c", "git log")`.
- **TTL**: 30d
```

### Knowledge State Properties

| Property | Type | Purpose |
|---|---|---|
| `id` | String | Unique identifier (e.g., LESSON-001) |
| `ttl_days` | Integer | Time to live before pruning |
| `active` | Boolean | Whether to inject in prompt context |

---

## ❌ Anti-Patterns & Pitfalls to Avoid

- **Anti-Pattern (Monolithic Context)**: Don't inject all lessons at once. This wastes tokens. Only inject relevant ones.
- **Anti-Pattern (Stale Lessons)**: Avoid keeping expired lessons active. If they are no longer useful, prune them.
- **Anti-Pattern (Raw Injection)**: Never inject raw unformatted text. Ensure it matches the markdown schema of prompt templates.
- **Anti-Pattern (Bypassing Checks)**: Don't disable the injection verification step, as it prevents agents from learning from previous failures.
