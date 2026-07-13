---
name: mcp-lean-ctx
description: "Mastery of the lean-ctx Model Context Protocol (MCP) server. Guides agents on context budgeting, token usage checks, and payload compression."
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
version: 1.0.0
---

# MCP Lean Context Skill

> Monitor token budgets, compress payloads, and prevent context window exhaustion using the `lean-ctx` MCP server.

## 🎯 When to Use This Skill

- **Trigger**: When the context size is high or approaching system limitations.
- **Trigger**: Before loading large text or structured JSON payloads into the LLM context.
- **Trigger**: When monitoring token cost or measuring current request footprint.

---

## 📋 Context Management Guidelines & Rules

### 1. Payload Compression Rules
- **Rule 1**: If a tool output or file read size exceeds 200 tokens, it **must** be sent to `lean-ctx` for compression before context injection.
- **Rule 2**: Check current token usage metrics before spawning nested tool execution loops.
- **Rule 3**: Store compressed archives in `.agent/tmp/llm_cache/` or respective session scopes.

### 2. Context Window Monitoring
- **Rule 4**: Monitor context headroom. If the token count exceeds 80% of the maximum limit, immediately prune low-priority history entries.

---

## 💻 Code Examples & Compression Patterns

### Compressing Tool Output

```json
// Example payload for compressing file contents using headroom-mcp
{
  "serverName": "headroom-mcp", // or "lean-ctx" in cluster namespace
  "toolName": "headroom_compress",
  "arguments": {
    "content": "Large text data to be compressed for token efficiency..."
  }
}
```

### Context Threshold Actions

| Context Usage | Required Action | Outcome |
|---|---|---|
| `< 50%` | Normal operations | Standard logs |
| `50% - 80%` | Compress outputs > 200 tokens | Saved context tokens |
| `> 80%` | Prune session history, activate maximum compression | Prevent context truncation error |

---

## ❌ Anti-Patterns & Pitfalls to Avoid

- **Anti-Pattern (Dumping Raw Logs)**: Avoid injecting huge stack traces or verbose log outputs directly to context. Always use `lean-ctx` to summarize.
- **Anti-Pattern (Bypassing Headroom)**: Never ignore context budget warnings. Continuing execution with a saturated context window causes truncation and model confusion.
- **Anti-Pattern (Compression Overhead)**: Don't compress small payloads (< 100 tokens), as the compression tool overhead exceeds token savings.
- **Anti-Pattern (Losing Critical Context)**: Avoid pruning critical invariants or instructions. Only prune session chat history.

---

## Additional Quality Guidelines
To ensure the highest standard of delivery, the following additional considerations must be met:
1. Maintain consistency with existing naming conventions in the codebase.
2. Implement comprehensive error handling and logging for all new components.
3. Ensure that all dependencies are declared and verified beforehand.
4. Write clean, self-documenting code with clear comments where necessary.
5. Validate performance under load and avoid premature optimizations.
