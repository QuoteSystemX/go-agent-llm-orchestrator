---
name: mcp-builder
description: MCP (Model Context Protocol) server building principles. Tool design, resource patterns, best practices.
allowed-tools: Read, Write, Edit, Glob, Grep
version: 1.0.0
---

# MCP Builder

> Principles for building MCP servers.

---

## 1. MCP Overview

### What is MCP?

Model Context Protocol - standard for connecting AI systems with external tools and data sources.

### Core Concepts

| Concept | Purpose |
|---------|---------|
| **Tools** | Functions AI can call |
| **Resources** | Data AI can read |
| **Prompts** | Pre-defined prompt templates |

---

## 2. Server Architecture

### Project Structure

```
my-mcp-server/
├── src/
│   └── index.ts      # Main entry
├── package.json
└── tsconfig.json
```

### Transport Types

| Type | Use |
|------|-----|
| **Stdio** | Local, CLI-based |
| **SSE** | Web-based, streaming |
| **WebSocket** | Real-time, bidirectional |

---

## 3. Tool Design Principles

### Good Tool Design

| Principle | Description |
|-----------|-------------|
| Clear name | Action-oriented (get_weather, create_user) |
| Single purpose | One thing well |
| Validated input | Schema with types and descriptions |
| Structured output | Predictable response format |

### Input Schema Design

| Field | Required? |
|-------|-----------|
| Type | Yes - object |
| Properties | Define each param |
| Required | List mandatory params |
| Description | Human-readable |

---

## 4. Resource Patterns

### Resource Types

| Type | Use |
|------|-----|
| Static | Fixed data (config, docs) |
| Dynamic | Generated on request |
| Template | URI with parameters |

### URI Patterns

| Pattern | Example |
|---------|---------|
| Fixed | `docs://readme` |
| Parameterized | `users://{userId}` |
| Collection | `files://project/*` |

---

## 5. Error Handling

### Error Types

| Situation | Response |
|-----------|----------|
| Invalid params | Validation error message |
| Not found | Clear "not found" |
| Server error | Generic error, log details |

### Best Practices

- Return structured errors
- Don't expose internal details
- Log for debugging
- Provide actionable messages

---

## 6. Multimodal Handling

### Supported Types

| Type | Encoding |
|------|----------|
| Text | Plain text |
| Images | Base64 + MIME type |
| Files | Base64 + MIME type |

---

## 7. Security Principles

### Input Validation

- Validate all tool inputs
- Sanitize user-provided data
- Limit resource access

### API Keys

- Use environment variables
- Don't log secrets
- Validate permissions

---

## 8. Configuration

### Claude Desktop Config

| Field | Purpose |
|-------|---------|
| command | Executable to run |
| args | Command arguments |
| env | Environment variables |

---

## 9. Testing

### Test Categories

| Type | Focus |
|------|-------|
| Unit | Tool logic |
| Integration | Full server |
| Contract | Schema validation |

---

## 10. Best Practices Checklist

- [ ] Clear, action-oriented tool names
- [ ] Complete input schemas with descriptions
- [ ] Structured JSON output
- [ ] Error handling for all cases
- [ ] Input validation
- [ ] Environment-based configuration
- [ ] Logging for debugging

---

> **Remember:** MCP tools should be simple, focused, and well-documented. The AI relies on descriptions to use them correctly.

## Changelog

- **1.0.0** (2026-04-26): Initial version

## When to Use

- **Adding a new MCP tool to a server** — define the JSON schema,
  add to the server's tool list, document in `mcp_config.json`.
- **Designing tool schemas** — keep parameters flat, use clear
  descriptions (the AI reads them).
- **Testing MCP tools** — use the `mcp-llm-broker` test mode
  with `--dry-run` to verify schemas parse correctly.
- **Migrating from REST APIs to MCP** — wrap each endpoint as
  a tool with a structured input/output schema.
- **Building domain-specific MCP servers** — e.g., a database
  query tool, a file search tool, a CI trigger tool.

Avoid using this skill for:
- Building regular APIs (use `api-patterns`).
- Simple shell scripts (use `bash-linux`).
- One-off tools that won't be reused.

## Anti-Patterns

- **Don't create too many tools in one server** — agents get
  overwhelmed. Group related tools (e.g., a `db` server with
  query, schema, and migrate, not 20 separate servers).
- **Don't use vague descriptions** — the AI uses descriptions to
  decide which tool to call. "queries the database" is bad;
  "queries users by name and returns id, email, role" is good.
- **Don't expose internal-only state as a tool parameter** — if
  the agent doesn't need to know, don't make it set it.
- **Don't return unstructured text** — return JSON. Agents parse
  JSON reliably; prose is harder.
- **Don't use complex nested schemas** — keep parameters flat.
  If you have nested config, take a config object as a single
  string field instead.
- **Don't skip the `required` field** — every required parameter
  must be in the `required` array. Optional params go OUT of
  `required`.
- **Don't name tools with verbs that overlap** — `search` vs
  `find` vs `query` confuses the agent. Use consistent naming
  per server.
