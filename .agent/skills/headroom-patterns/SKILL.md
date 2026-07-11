---
name: headroom-patterns
tags: [compression, tokens, performance, mcp, headroom, context]
description: Patterns for using Headroom to compress context before passing to LLM. Reduces token consumption by 60-95% without quality loss.
---

# 🗜️ Headroom Patterns — Context Compression for LLMs

Use this skill to reduce token consumption when working with large tool outputs, files, logs, or structured data that would bloat the LLM context window.

---

## 📌 When To Use This Skill

Invoke `headroom_compress` **BEFORE** adding content to LLM context when:
- Tool output (grep, find, diff, log) exceeds **200 tokens**.
- A RAG chunk or full file exceeds **300 tokens**.
- A JSON structure with repeating fields exceeds **150 tokens**.
- Any stack trace or log file regardless of size.

---

## 🔧 Instructions — How To Apply

### Step 1: Capture Tool Output
```python
result = bash("grep -r 'pattern' src/")
```

### Step 2: Compress Before Context Injection
```python
compressed = headroom_compress(content=result, content_type="code")
# Returns: {compressed_id, compressed_content, token_savings_pct, original_tokens}
```

### Step 3: Work With Compressed Content
```python
# LLM operates on compressed_content — calls headroom_retrieve when detail is needed
original = headroom_retrieve(compressed_id)
```

### Step 4: Bus Artifacts > 500 tokens — Store `compressed_id` Only
```python
# ✅ Store only the ID, not the full content
bus_artifact["content"] = compressed["compressed_id"]
bus_artifact["_ccr"] = True
```

---

## 📊 Content Type Reference

| `content_type` | When To Apply | Compressor Used |
| :--- | :--- | :--- |
| `code` | Source code, diffs, patches, stack traces | CodeCompressor (AST-aware) |
| `json` | API responses, configs, JSON logs | SmartCrusher |
| `text` | Prose, documentation, README | Kompress-base |
| `log` | Log files, build output | SmartCrusher + deduplication |

---

## 📈 Monitoring Compression Savings

```python
headroom_stats()
# Returns:
# {
#   total_compressed: N,
#   avg_savings_pct: 72.4,
#   cache_hits: N,
#   top_content_types: ["code", "json"]
# }
```

---

## 🔗 Bus Integration

If a bus object has `_ccr: true`, its `content` field is compressed.

```python
# Retrieve full content when needed
original = pull_with_ccr(id, retrieve_full=True)
```

---

## ⚠️ Anti-Patterns & When NOT To Use

- ❌ **Never compress user input**: Human messages must reach the LLM unmodified.
- ❌ **Don't compress short outputs**: If result is < 100 tokens, pass it directly — overhead is not worth it.
- ❌ **Don't compress already-compressed data**: Check for `compressed_id` field before compressing again.
- ❌ **Don't compress security artifacts**: Passwords, API keys, auth tokens — never pass through Headroom.
- ❌ **Don't ignore `_ccr` flag**: If a bus artifact has `_ccr: true`, always use `headroom_retrieve` before processing.

---

## ✅ Quick Decision Checklist

| Condition | Action |
| :--- | :--- |
| Tool output > 200 tokens | `headroom_compress(type="code"\|"log")` |
| JSON response > 150 tokens | `headroom_compress(type="json")` |
| Prose / docs > 300 tokens | `headroom_compress(type="text")` |
| Bus artifact > 500 tokens | Store `compressed_id` only |
| User message (any size) | Pass directly — no compression |
| Already has `compressed_id` | Skip — already compressed |
