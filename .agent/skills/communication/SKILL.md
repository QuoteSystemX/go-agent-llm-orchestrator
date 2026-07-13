---
name: communication
description: Manage agent communication style, structure human-to-agent interface protocols, and handle live feedback/acknowledgement loops.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
version: 1.0.0
---

# Communication Skill

> Establish high-bandwidth, precise, and transparent communication between agents and human operators.

## 🎯 When to Use This Skill

- **Trigger**: Structuring responses, plans, and final walkthroughs for the human user.
- **Trigger**: Emitting progress events, acks, or checkpoints on the shared context bus.
- **Trigger**: Formulating Socratic questions to resolve plan ambiguity or clarify user intent.
- **Trigger**: Formatting reports, tables, or markdown artifacts for optimal readability.

---

## 📋 Communication Protocols & Rules

### 1. Human-to-Agent Communication (INBOX)

When consuming or responding to `tasks/INBOX.md` entries, follow these rules:
- **Rule 1 (Immediate Acknowledgment)**: Read incoming entries at the start of a task cycle and update their status.
- **Rule 2 (Clear Intent Matching)**: Always map user requests to the 5 supported intents (redirect, clarify, abort, context, ack).
- **Rule 3 (Sanitized Outputs)**: Never output raw Markdown formatting (like nested blocks or unescaped tags) to channels expecting sanitized fields.

### 2. Live Telemetry & Event Logging

- **OTel Integration**: Report token usage, latencies, and execution status using the standard logger.
- **Dashboard Updates**: Always push metrics to the local EventSource server (`bus_sse_server.py`) to keep the web dashboard in sync.

### 3. Formatting & References

- **Rule 4 (File Links)**: You must format files, directories, and code symbols as clickable local filesystem links (e.g., `[main.go](file:///path/to/main.go)`).
- **Rule 5 (Clarity)**: Keep explanations concise. Avoid verbose meta-commentary unless explicitly requested by the user.

---

## 💻 Code Examples & Formatting Patterns

### Clickable File Links formatting

| Incorrect Link (Broken) | Correct Link (Clickable) |
|---|---|
| `` `main.go` `` | `[main.go](file:///home/amudrykh/go/project/prompt-library/main.go)` |
| `path/to/file` | `[file.go](file:///home/amudrykh/go/project/prompt-library/path/to/file)` |

### Logging Telemetry Events

```python
# Standard pattern to log latency and tokens
log_event(
    agent="frontend-specialist",
    metric="latency_ms",
    value="4500",
    meta={"step": "ui-render"}
)
```

---

## ❌ Anti-Patterns & Pitfalls to Avoid

- **Anti-Pattern (Raw Output)**: Don't output long unformatted JSON dumps. Always wrap them in code blocks or tables.
- **Anti-Pattern (Vague Questions)**: Avoid asking open-ended questions like "What should I do next?". Instead, formulate concrete choices using Socratic options.
- **Anti-Pattern (Silent Failures)**: Never fail silently. When a tool command outputs an error, always log it on the context bus.
- **Anti-Pattern (Markdown in JSON)**: Avoid placing unescaped Markdown syntax inside JSON fields, as it breaks downstream parsers.
