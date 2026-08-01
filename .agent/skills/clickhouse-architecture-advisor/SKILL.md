---
name: clickhouse-architecture-advisor
description: "Workload-aware ClickHouse architecture decision frameworks — ingestion strategy, partitioning strategy, JOIN/dimension enrichment path, late-arriving/mutable data, and real-time pre-aggregation. Adapted from the official ClickHouse Agent Skills (Apache-2.0). Use for whole-workload design decisions, not single-query optimization — pair with the clickhouse-best-practices skill for per-rule guidance."
version: 1.0.0
---

# ClickHouse Architecture Advisor

Five decision frameworks for workload-level ClickHouse architecture choices, where "it depends"
actually depends on something concrete (throughput, dimension volatility, freshness needs). Prefer
official docs over these when they conflict — these frameworks synthesize documented patterns into
condition→recommendation tables, they don't override the docs.

When recommending, be explicit about confidence: **official** (directly documented), **derived**
(follows logically from documented behavior), or **field** (heuristic/situational) — don't present
field guidance as official.

## 1. Ingestion Strategy

| Condition | Recommendation |
|---|---|
| Producers can batch to 10K–100K rows, latency tolerance moderate | Direct batched inserts |
| Many small inserts, producers can't batch | Async inserts (`async_insert=1`) |
| Bursty producers, many independent writers, need decoupling | Kafka engine + materialized view |
| Reliability/replay/fan-out are primary concerns | Upstream queue/log broker before ClickHouse |

## 2. Time-Series Partitioning

| Condition | Recommendation |
|---|---|
| Early-stage or unclear retention needs | Start without partitioning |
| Month-scale retention windows | Monthly partitioning (`toStartOfMonth`) |
| Strictly day-bounded queries, short retention | Daily partitioning, only if partition count stays bounded |
| High-scale time-series with TTL/bulk expiration | Partition aligned to the retention operation's time unit |

Partitioning is a lifecycle/pruning tool, not a query accelerator — that's ORDER BY's job (see
`clickhouse-best-practices`). Verify: count active partitions, confirm queries actually align to
the partition key, confirm retention ops (DROP PARTITION) operate at partition granularity.

## 3. JOIN / Dimension Enrichment Path

| Condition | Recommendation |
|---|---|
| Small, slowly-changing lookup table, used in many queries | Dictionary |
| Dimension is stable, storage duplication acceptable | Denormalize |
| Complex join logic, refreshed on a schedule | Refreshable materialized view |
| Exploratory/infrequent query, dimensions change often | Runtime JOIN |

Not every dimension lookup should stay a runtime JOIN — the right choice depends on dimension
volatility, cardinality, and how often the enrichment repeats. Validate by identifying top
CPU-consuming JOIN patterns and comparing runtime-JOIN cost against a dictionary or precomputed
alternative before committing to a redesign.

## 4. Late-Arriving Data & Mutable State

| Condition | Recommendation |
|---|---|
| Immutable event log, latest-state queries | Raw append table + latest-state query/MV |
| Natural replacement semantics with version ordering | `ReplacingMergeTree` |
| Explicit row-state transitions modeled | `CollapsingMergeTree` / `VersionedCollapsingMergeTree` |
| Small, infrequent, operationally bounded corrections | Targeted mutation may be acceptable (field) |

`ALTER TABLE UPDATE`/`DELETE` is usually the wrong first answer — prefer append-friendly patterns
and engines built for state evolution (see `insert-strategy.md` in `clickhouse-best-practices`).
Measure mutation volume/day and confirm the workload is actually latest-state rather than true OLTP
before reaching for mutations.

## 5. Real-Time Pre-Aggregation

| Condition | Recommendation |
|---|---|
| Ad hoc queries, freshness matters most | Query raw tables |
| Repeated aggregation over append-only data | Incremental materialized view |
| Complex joins or scheduled batch recomputation | Refreshable materialized view |
| Very hot dashboard/alerting path | Incremental rollup table + raw-table fallback |

Real-time workloads shouldn't be forced into "everything raw" or "precompute everything" — pick
based on freshness requirement, query repetition, and transformation complexity. Identify the
repeated dashboard queries first; that's usually where pre-aggregation pays for itself.

## Output Format

```markdown
## Workload Summary
- workload / latency target / data shape / primary query patterns / operational constraints

## Key Decisions
- ...

## Recommendations
### <Title>
**What** ... **Why** ... **How** ...
**Category**: official | derived | field
**Source**: doc link(s)
**Validation**: concrete SQL/metric/smoke test
```

## Source & Attribution

Adapted from [ClickHouse/agent-skills](https://github.com/ClickHouse/agent-skills)
(`clickhouse-architecture-advisor`, v0.1.0), © ClickHouse Inc, Apache-2.0.

## Changelog

- **1.0.0** (2026-08-01): Initial version, ported from ClickHouse/agent-skills v0.1.0.
