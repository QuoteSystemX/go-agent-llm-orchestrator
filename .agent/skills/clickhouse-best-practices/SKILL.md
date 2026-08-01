---
name: clickhouse-best-practices
description: "ClickHouse schema design, query optimization, insert strategy, and AI-agent connectivity rules, adapted from the official ClickHouse Agent Skills (Apache-2.0). Use when creating/altering ClickHouse tables, choosing ORDER BY/PARTITION BY, writing or reviewing JOINs, designing insert pipelines, or connecting an agent to ClickHouse. Triggers on ClickHouse, MergeTree, ORDER BY, PARTITION BY, LowCardinality, ReplacingMergeTree, async_insert."
version: 1.0.0
---

# ClickHouse Best Practices

Condensed, agent-oriented guidance distilled from ClickHouse Inc's official Agent Skills package.
Covers the parts of the 31-rule official ruleset that generalize across projects — see
[references/](references/) for the full detail behind each category. For anything not covered
here, prefer the [official docs](https://clickhouse.com/docs/best-practices) over guessing —
ClickHouse's storage model (columnar, sparse index, MergeTree) makes general-database intuition
misleading in several places below.

## Non-negotiables (read first)

1. **ORDER BY is immutable.** Analyze query patterns *before* `CREATE TABLE` — changing it later means migrating all data. See [references/schema-design.md](references/schema-design.md).
2. **Every agent-generated query needs a LIMIT + scan cap + timeout**, or it can scan billions of rows. See [references/agent-integration.md](references/agent-integration.md).
3. **Never use `ALTER TABLE UPDATE/DELETE`** for routine changes — they rewrite whole parts. Use `ReplacingMergeTree`/`CollapsingMergeTree` or lightweight UPDATE/DELETE instead. See [references/insert-strategy.md](references/insert-strategy.md).
4. **Batch inserts 10K–100K rows.** Single-row inserts create a part per insert and destabilize the cluster. See [references/insert-strategy.md](references/insert-strategy.md).

## Decision Tree — which reference to read

**Designing or reviewing `CREATE TABLE` / `ALTER TABLE`?**
→ Read [references/schema-design.md](references/schema-design.md) — ORDER BY/PK selection, data types, partitioning, JSON.

**Writing or reviewing a SELECT with JOINs, filters, or aggregations?**
→ Read [references/query-optimization.md](references/query-optimization.md) — JOIN algorithms, skip indices, materialized views.

**Designing a data-ingestion path (batch or streaming)?**
→ Read [references/insert-strategy.md](references/insert-strategy.md) — batch sizing, async inserts, mutation avoidance.

**Building or configuring an agent/MCP integration against ClickHouse?**
→ Read [references/agent-integration.md](references/agent-integration.md) — schema discovery workflow, query safety limits, connection setup.

**Deciding overall workload architecture (ingestion strategy, partitioning strategy, enrichment path, real-time pre-aggregation)?**
→ Use the sibling skill `clickhouse-architecture-advisor` — those are workload-level decisions, not per-query rules.

## Agent Session Sequence

1. **Connect** — MCP or CLI, credentials pre-configured (never prompt per-session).
2. **Discover** — databases → tables → columns+comments → sort key → skip indices → sample → `EXPLAIN`.
3. **Plan** — use the sort key and skip-index knowledge to write WHERE clauses that actually prune.
4. **Execute** — always with `LIMIT` + `max_rows_to_read`/`max_bytes_to_read` + `max_execution_time`.
5. **Recover** — on timeout/memory error, narrow filters and retry; don't just raise the limit.

## Priority Quick Reference

| Priority | Category | Rule prefix | Where |
|---|---|---|---|
| CRITICAL | Primary key / ORDER BY selection | `schema-pk-*` | schema-design.md |
| CRITICAL | Data type selection | `schema-types-*` | schema-design.md |
| CRITICAL | JOIN optimization | `query-join-*` | query-optimization.md |
| CRITICAL | Insert batching & mutation avoidance | `insert-batch-*`, `insert-mutation-*` | insert-strategy.md |
| CRITICAL | Agent schema discovery & query safety | `agent-discovery-*`, `agent-query-*` | agent-integration.md |
| HIGH | Partitioning strategy | `schema-partition-*` | schema-design.md |
| HIGH | Skip indices, materialized views | `query-index-*`, `query-mv-*` | query-optimization.md |
| HIGH | Async inserts, OPTIMIZE avoidance | `insert-async-*`, `insert-optimize-*` | insert-strategy.md |
| MEDIUM | JSON column usage, Enum types | `schema-json-*`, `schema-types-enum` | schema-design.md |

## Output Format When Reviewing ClickHouse Code

```
## Rules Checked
- `rule-name` - Compliant / Violation found

## Findings
### Violations
- **`rule-name`**: Current: [...] Required: [...] Fix: [...]
### Compliant
- `rule-name`: Brief note

## Recommendations
[Prioritized, citing rules]
```

## Source & Attribution

Content adapted from [ClickHouse/agent-skills](https://github.com/ClickHouse/agent-skills)
(`clickhouse-best-practices`, v0.4.0), © ClickHouse Inc, Apache-2.0. Condensed for this repo's
skill format — for the full 31-rule expanded reference with all SQL examples, see the upstream
`AGENTS.md` in that repo, or [clickhouse.com/docs/best-practices](https://clickhouse.com/docs/best-practices).

## Changelog

- **1.0.0** (2026-08-01): Initial version, ported from ClickHouse/agent-skills v0.4.0.
