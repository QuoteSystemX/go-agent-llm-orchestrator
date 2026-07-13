---
name: mcp-codebase-memory
description: "Mastery of the codebase-memory Model Context Protocol (MCP) server. Guides agents on semantic searches, AST symbol lookups, relationship tracing, and codebase graph analysis."
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
version: 1.0.0
---

# MCP Codebase Memory Skill

> Interact with the multi-replica `codebase-memory` MCP servers to query symbols, files, and architectural relationships across the workspace.

## 🎯 When to Use This Skill

- **Trigger**: When tracing symbol definitions, usages, and AST structures of code files.
- **Trigger**: When querying replica services `codebase-memory-0`, `codebase-memory-1`, or `codebase-memory-2`.
- **Trigger**: Before modifying file dependencies, to identify all affected components in the dependency graph.

---

## 📋 Querying Guidelines & Rules

### 1. Replica Load Balancing
- **Rule 1**: Always query `codebase-memory-0` as the default endpoint for symbol lookups.
- **Rule 2**: When running parallel tasks, distribute search queries across replicas (`-1` and `-2`) to prevent socket timeouts.
- **Rule 3**: Do not run write/indexing commands in parallel on different replicas; always synchronize write state.

### 2. AST and Semantic Analysis
- **Rule 4**: Use semantic search instead of full file read if the file is larger than 1000 lines.
- **Rule 5**: Always check definitions and references when refactoring Go types or structs.

---

## 💻 Code Examples & Search Patterns

### Graph-Augmented Code Search

```json
// Example payload for finding text pattern via codebase-memory search_code
{
  "serverName": "codebase-memory-0",
  "toolName": "search_code",
  "arguments": {
    "project": "home-amudrykh-go-project-prompt-library",
    "pattern": "InitTracer",
    "mode": "compact"
  }
}
```

### Replica Configuration

| Endpoint Replica | Domain Name | Target Query Load |
|---|---|---|
| `codebase-memory-0` | `multica-daemon-0.multica-daemon-headless` | Primary queries, symbol lookup |
| `codebase-memory-1` | `multica-daemon-1.multica-daemon-headless` | Parallel query load |
| `codebase-memory-2` | `multica-daemon-2.multica-daemon-headless` | AST relationships, background check |

---

## ❌ Anti-Patterns & Pitfalls to Avoid

- **Anti-Pattern (Raw Grep Flooding)**: Avoid running huge unguided grep commands when the codebase memory has semantic indexing tools.
- **Anti-Pattern (Overloading Replica 0)**: Don't route all concurrent queries to replica 0 when other replicas are available.
- **Anti-Pattern (Ignoring AST Schema)**: Never assume a struct shape without querying its semantic definition first.
- **Anti-Pattern (Stale Graph)**: Avoid querying codebase memory without refreshing the index after major file additions.

---

## Additional Quality Guidelines
To ensure the highest standard of delivery, the following additional considerations must be met:
1. Maintain consistency with existing naming conventions in the codebase.
2. Implement comprehensive error handling and logging for all new components.
3. Ensure that all dependencies are declared and verified beforehand.
4. Write clean, self-documenting code with clear comments where necessary.
5. Validate performance under load and avoid premature optimizations.
