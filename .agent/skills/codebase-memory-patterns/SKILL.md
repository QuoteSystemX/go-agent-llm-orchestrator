---
name: codebase-memory-patterns
description: Guidelines on using codebase-memory-mcp tools to query call graphs, dependencies, and class hierarchies instead of using verbose sequential grep searches.
version: 2.0.0
---

# Codebase Memory MCP Skill

This skill defines the patterns and best practices for leveraging the `codebase-memory-mcp` knowledge graph server (DeusData/codebase-memory-mcp, currently v0.10.8) to perform highly efficient codebase research and analysis.

## Core Principle

> [!IMPORTANT]
> **Token-Saving Rule (P0):** Never search the entire workspace using raw `grep` or read multiple source files sequentially to map code relationships. Use `codebase-memory` MCP tools first.
> Querying the graph fetches targeted structure maps instead of massive text buffers, reducing token footprint in the context window by up to **99%**.

The server's own `initialize` response carries this guidance verbatim (source of truth — re-check it if this skill and a live server ever disagree):

> Use graph tools first for structural code discovery: `search_graph` to find symbols, `trace_path` for callers and callees, `get_code_snippet` for exact source, `query_graph` for complex multi-hop patterns, and `get_architecture` for orientation. Use `search_code` or filesystem grep for literal or non-code text, or when graph coverage is insufficient. Call `list_projects` before initial use and `index_repository` only when a repository is not indexed or to force immediate freshness after a large external update. Once indexed, watched projects auto-refresh in the background; use `index_status` for project health and `check_index_coverage` for every cited path and for scopes behind negative or exhaustive claims. Coverage is best-effort, never proof of completeness. Check `has_more`/`nextCursor` and paginate when present.

---

## Available Tools (verified against the live server's `tools/list`)

| Tool | Use it for |
| --- | --- |
| `list_projects` | First call each session — see what's already indexed. |
| `index_repository` | Build/refresh the graph for a repo not yet indexed, or force freshness after a large external change. Not needed every turn — watched projects auto-refresh. |
| `search_graph` | Find symbols/functions/classes/routes. Three modes: `query` (BM25 full-text, natural language), `name_pattern` (regex), `semantic_query` (vector search bridging vocabulary, e.g. "send" finds "publish"). Use INSTEAD OF grep for code definitions. |
| `trace_path` | Callers/callees (`mode=calls`), value propagation (`mode=data_flow`), or cross-service HTTP/async chains (`mode=cross_service`). Use INSTEAD OF grep for "who calls this" or impact analysis. |
| `get_code_snippet` | Read source for a symbol. Call `search_graph` first to get the exact `qualified_name`. |
| `query_graph` | Cypher query for complex multi-hop patterns, aggregations, hot-path/complexity analysis (cyclomatic complexity, loop depth, unguarded recursion, etc.). |
| `get_architecture` | High-level orientation: overview, structure, dependencies, routes, hotspots, boundaries, layers, clusters (Leiden community detection — real architectural seams, not just folder layout), file_tree, cycles. |
| `search_code` | Graph-augmented grep: text search enriched with structural ranking (definitions first, tests last). Use for literal/non-code text or when graph coverage is insufficient. |
| `index_status` | Node/edge counts, git context, and which files the indexer could NOT fully cover (best-effort — check before trusting completeness). |
| `check_index_coverage` | Authoritative coverage check for specific paths/scopes. Use before any negative/exhaustive claim ("X is not used anywhere") and for every file you cite. |
| `detect_changes` | Map a git diff to its blast radius — transitive callers (or dependents) of changed symbols. Use before/after a refactor instead of manually tracing impact. |
| `manage_adr` | Create/update/list Architecture Decision Record sections. |
| `ingest_traces` | Feed runtime caller→callee traces into the graph to enhance it. |
| `list_projects` / `delete_project` | Manage multiple indexed projects. |

---

## Workflow Patterns

### 1. Codebase Exploration (New Feature or Bug Investigation)
* **Goal:** Understand where to place new code or where a bug propagates.
* **Incorrect Workflow:** `Grep` the bug symptom -> `Read` 10 files one by one to trace how values are passed.
* **Correct Workflow:**
  1. `search_graph` (query or semantic_query) to find the relevant symbol.
  2. `trace_path` (mode=calls or data_flow) to see callers/callees/value flow.
  3. `get_code_snippet` with the exact `qualified_name` to read the real source.
  4. `trace_path` (mode=cross_service) if it crosses an HTTP/async boundary.

### 2. Dependency / Impact Auditing (Before a Refactor)
* **Goal:** Know the blast radius before changing a shared symbol.
* **Workflow:**
  1. `detect_changes` (scope=impact) against the target branch/ref to get the transitive impact set from a diff, or
  2. `trace_path` (mode=calls, direction=inbound) on a specific symbol for its full caller set.
  3. `check_index_coverage` on the touched paths — don't trust a clean result if coverage is incomplete.

### 3. Architecture / Community Overview
* **Goal:** Understand high-level system components and real module boundaries.
* **Workflow:** `get_architecture` with `aspects: ["clusters"]` (Leiden community detection) or `["all"]` for a full picture.

### 4. Hot-Path / Complexity Queries
* **Goal:** Find risky functions (nested loops, unguarded recursion, O(n²) scans) ahead of a performance pass.
* **Workflow:** `query_graph` with a Cypher query over `complexity`, `loop_depth`, `transitive_loop_depth`, `linear_scan_in_loop`, `unguarded_recursion`, etc.

---

## Context Window Optimization

- Prefer `search_graph`/`trace_path` `detail: "ids"` or narrow filters (`label`, `file_pattern`, `min_degree`) before paginating large result sets.
- All list-shaped tools return `total` + `has_more`/`next` — check it and paginate with `offset`/`cursor` rather than assuming a single call returned everything.

## When to Use

- **"Who calls this function?"** — `trace_path` (mode=calls), not grep.
- **Understanding a class/symbol's definition or relationships** — `search_graph`.
- **Impact of a change / circular dependency risk** — `detect_changes` or `trace_path` (direction=inbound), not manual import-reading.
- **Cross-service call chains** — `trace_path` (mode=cross_service).
- **System orientation on an unfamiliar repo** — `get_architecture`.
- **Before any refactor** — trace the impact graph first.

Avoid using this skill for:
- Simple literal text searches (use `search_code` or `Grep` directly).
- Reading documentation (use `Read`).
- Runtime behavior (use logging/metrics; `ingest_traces` only feeds observed call counts back into the graph, it doesn't observe them itself).

## Anti-Patterns

- **Don't grep the entire workspace for symbol references** — use `search_graph` / `trace_path`. Grep returns text; the graph returns structured relationships.
- **Don't read multiple source files sequentially to map a call graph** — that's exactly what `trace_path` is for.
- **Don't use `query_graph` for simple lookups** — use `search_graph`/`trace_path` for clarity and performance; reserve Cypher for genuinely multi-hop/aggregate questions.
- **Don't treat coverage as absolute** — every read-heavy tool response is best-effort (`parse_partial`/`skipped` files exist). Run `check_index_coverage` before an exhaustive or negative claim, and grep the flagged ranges directly.
- **Don't re-index on every turn** — indexed projects auto-refresh in the background; only call `index_repository` when a project isn't indexed yet or after a large external update.
- **Don't fall back to `Grep`/`Read` silently just because it's the default** — if `codebase-memory` tools are unavailable this session (MCP failed to connect), that's fine, but prefer them whenever they're connected.
