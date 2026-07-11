---
name: MCP Integration Standards
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
