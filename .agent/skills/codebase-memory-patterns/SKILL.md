---
name: codebase-memory-patterns
description: Guidelines on using codebase-memory-mcp tools to query call graphs, dependencies, and class hierarchies instead of using verbose sequential grep searches.
version: 1.0.0
---

# Codebase Memory MCP Skill

This skill defines the patterns and best practices for leveraging the `codebase-memory-mcp` knowledge graph server to perform highly efficient codebase research and analysis.

## Core Principle

> [!IMPORTANT]
> **Token-Saving Rule (P0):** Never search the entire workspace using raw `grep` or read multiple source files sequentially to map code relationships. Use `codebase-memory` MCP tools first.
> Querying the graph fetches targeted structure maps instead of massive text buffers, reducing token footprint in the context window by up to **99%**.

---

## Available Tools (Graph Queries)

The `codebase-memory` MCP server exposes tools to interact with the local Tree-sitter indexed knowledge graph:

1. **`get_callers`**: Find all functions/methods calling a given target symbol.
2. **`get_callees`**: Find all functions/methods called by a given target symbol.
3. **`get_symbol_definitions`**: Locate where a class, function, struct, or variable is defined.
4. **`get_dependencies`**: Track file/package import dependencies.
5. **`get_http_routes`**: Trace API endpoints and cross-service HTTP call chains.
6. **`execute_graph_query`**: Execute a Cypher-like query for complex, ad-hoc codebase pattern matching.

---

## Workflow Patterns

### 1. Codebase Exploration (New Feature or Bug Investigation)
* **Goal:** Understand where to place new code or where a bug propagates.
* **Incorrect Workflow:** Run `grep_search` on the bug symptom -> Read 10 files one by one to trace how values are passed.
* **Correct Workflow:**
  1. Call `get_symbol_definitions` on the target function or struct.
  2. Call `get_callers` to see where it is invoked.
  3. Call `get_http_routes` if it relates to an API endpoint.

### 2. Dependency Auditing
* **Goal:** Check if importing a package creates circular dependencies.
* **Workflow:**
  1. Call `get_dependencies` for the target directories.
  2. Map out the imports using structural queries rather than reading the top of every file.

### 3. Louvain/Louvain Community Overviews
* **Goal:** Understand high-level system components.
* **Workflow:** Use `execute_graph_query` to query community tags and identify tightly-coupled modules.

---

## Context Window Optimization (Headroom Integration)

When a graph query returns large outputs:
- The `Headroom` middleware will automatically intercept and compress the output if it exceeds 500 tokens.
- Keep queries specific (e.g. limit by file extension or path) to avoid overloading the memory registry.

## When to Use

- **Investigating "who calls this function?"** — use `get_callers`
  instead of grepping for the function name.
- **Understanding a class hierarchy** — use `get_symbol_definitions`
  to find definitions and parent classes.
- **Tracing import dependencies** — use `get_dependencies`
  before refactoring shared modules.
- **Following HTTP call chains** — use `get_http_routes` for
  service-to-service traces.
- **Ad-hoc pattern queries** — use `execute_graph_query` with
  a Cypher-like syntax for complex relationship questions.
- **Before any refactor** — explore the impact graph first.

Avoid using this skill for:
- Simple text searches (use `Grep` tool directly).
- Reading documentation (use `Read` tool).
- Looking at runtime behavior (use logging/metrics).

## Anti-Patterns

- **Don't grep the entire workspace for symbol references** —
  use `get_callers` / `get_callees`. Grep returns text; the
  graph returns structured relationships.
- **Don't read multiple source files sequentially to map a
  call graph** — that's exactly what `get_callers` is for.
- **Don't use `execute_graph_query` for simple lookups** — use the
  specific tool (e.g., `get_symbol_definitions`) for clarity and
  performance.
- **Don't ignore the Headroom compression signal** — if a query
  returns compressed output, the query is too broad. Narrow it.
- **Don't query the graph for runtime state** — it's a static
  code graph, not a runtime profiler. Use metrics/traces for that.
- **Don't skip the index build** — if the graph returns no
  results, the index may be stale. Rebuild with
  `codebase-memory-mcp build-index`.
