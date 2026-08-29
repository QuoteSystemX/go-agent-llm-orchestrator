---
name: mcp-integration-standards
description: Guidelines for writing custom MCP servers, json-schema formatting, transport debugging, and API design.
---

# MCP Integration & Schema Standards

This skill defines the development guidelines and design patterns for building Model Context Protocol (MCP) servers and integrating them into agent platforms.

## 1. Schema & Design Best Practices

### A. Schema Completeness
Every MCP tool must be fully described with a JSON-Schema. Never rely on the LLM guessing parameters.

```json
{
  "name": "read_logs",
  "description": "Reads logs from a specified task ID with line limits.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "taskId": {
        "type": "string",
        "description": "The unique UUID of the task."
      },
      "limit": {
        "type": "integer",
        "default": 100,
        "description": "Maximum number of lines to return."
      }
    },
    "required": ["taskId"]
  }
}
```

### B. Descriptive Naming
*   Use `snake_case` for tool names.
*   Make tool names self-describing (e.g., `read_file` instead of `file_tool`).
*   Include descriptive prompts or instructions in tool outputs where appropriate.

---

## 2. Transport Layer Debugging

### A. stdio Transport Protocol
*   **Stdout Cleanliness**: MCP servers communicate over stdio. The server process **MUST NOT** print anything to `stdout` except valid JSON-RPC frames.
*   **Logging Redirects**: Redirect all debug logs, errors, and informational prints to `stderr`. Printing plain text to `stdout` will corrupt the JSON-RPC stream and break the connection.

### B. SSE Transport Protocol
*   Validate endpoint configuration and keep connections persistent.
*   Implement proper heartbeats and retry policies to maintain connectivity.


## When to Use

- **Building a new MCP server** — start with the official
  SDK (Python, Go, TypeScript, Rust).
- **Defining tool schemas** — keep parameters flat, use clear
  descriptions (the AI reads them).
- **Setting up authentication** — OAuth 2.1 for production,
  API keys for dev.
- **Testing MCP servers** — use the inspector + automated tests.
- **Publishing** — npm/PyPI/go module + clear docs.

Avoid using this skill for:
- MCP tool design (use `@mcp-builder`).
- MCP protocol internals (use `@mcp-protocol-engineer`).
- Single-purpose servers (use platform-specific skills).

## Anti-Patterns

- **Don't use OAuth 1.0** — use OAuth 2.1 or API keys. OAuth
  1.0 is deprecated.
- **Don't put credentials in tool descriptions** — they're for
  documentation, not secrets.
- **Don't return large objects in tool responses** — paginate or
  filter. Large responses break context windows.
- **Don't use `error` as a string field** — use a structured
  error object (code, message, details).
- **Don't skip tool versioning** — once an agent depends on a
  tool, breaking changes are painful. Add `version` to outputs.
- **Don't ignore MCP error codes** — use the standard error codes
  (-32600 to -32603) so clients can handle them.