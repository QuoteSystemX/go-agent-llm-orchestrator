# Agent Integration — Schema Discovery, Query Safety, Connectivity

## Discover schema before querying (CRITICAL)

Never assume table/column names. Skipping this causes full scans, wrong columns, wasted compute.

```sql
-- 1. Databases
SELECT name FROM system.databases WHERE name NOT IN ('system','information_schema','INFORMATION_SCHEMA');
-- 2. Tables + size (what's expensive to scan carelessly)
SELECT database, name, engine, total_rows, formatReadableSize(total_bytes) size FROM system.tables WHERE database = 'analytics' ORDER BY total_bytes DESC;
-- 3. Columns + comments (comments carry semantics MCP list_tables may not surface — query system.columns directly)
SELECT name, type, comment FROM system.columns WHERE database='analytics' AND table='events' ORDER BY position;
-- 4. Sort key — THE most important step for writing efficient filters
SELECT sorting_key, primary_key, partition_key FROM system.tables WHERE database='analytics' AND table='events';
-- 5. Skip indices — which non-sort-key filters are actually fast
SELECT name, type_full, expr, granularity FROM system.data_skipping_indices WHERE database='analytics' AND table='events';
-- 6. Sample data
SELECT * FROM analytics.events LIMIT 5;
-- 7. Verify plan before running an expensive query
EXPLAIN indexes = 1 SELECT event_type, count() FROM analytics.events WHERE event_date >= '2024-01-01' AND user_id='abc123' GROUP BY event_type;
-- Or a cheap cost estimate without running it:
EXPLAIN ESTIMATE SELECT * FROM analytics.events WHERE event_date >= '2024-01-01' AND user_id='abc123';
```

## Apply safety limits to every agent-generated query (CRITICAL)

A single unbounded query can scan billions of rows and saturate the cluster. Non-negotiable:

- `LIMIT` to cap returned rows (default 1000).
- `max_rows_to_read` / `max_bytes_to_read` — **`LIMIT` alone does not stop a full scan**; this is
  the real scan-size guardrail.
- `max_execution_time` (default 30) — pair with `timeout_before_checking_execution_speed = 0` to
  make it an actual wall-clock limit (its own default of 10 gives queries 10s of grace first).
- Never `SELECT *` on a large table without both `LIMIT` and scan caps.
- Never query without filtering on sort key / partition key columns.

```sql
SELECT * FROM events WHERE event_date >= today() - 7 AND user_id = '123'
LIMIT 100
SETTINGS max_execution_time = 30, max_rows_to_read = 1000000000, timeout_before_checking_execution_speed = 0;
```

**Self-hosted vs Cloud**: on self-hosted, `max_memory_usage`, scan caps, and execution-time caps
all default to unlimited (0) — set them explicitly, and note GROUP BY/ORDER BY have no automatic
memory ceiling unless you set `max_bytes_before_external_group_by`/`_sort`. Cloud bounds per-query
memory and spills GROUP BY/ORDER BY to disk automatically, but scan and time caps still need to be
set explicitly on both.

**On errors**: `TIMEOUT_EXCEEDED` → narrow the time range / add sort-key filters, check
`EXPLAIN ESTIMATE` before retrying. `MEMORY_LIMIT_EXCEEDED` → narrow filters, lower GROUP BY
cardinality, enable external spill — don't just raise the memory ceiling unless that's genuinely
the bottleneck. `TOO_MANY_PARTS` → back off insert rate, merges are behind; wait and retry.

Per-query `SETTINGS` only help if the agent remembers to emit them — for production, back them
with a read-only settings profile (`readonly=2`) on the agent's DB role, and quotas to bound
scanned bytes/requests per interval, so limits hold even when a query forgets them.

**Progressive exploration**: count first (cheap) → small `LIMIT`ed sample → full query with caps.
Don't jump straight to an unbounded aggregation over an unknown-size table.

## Connecting an agent

- **MCP** (interactive, multi-step analysis): `claude mcp add --transport http clickhouse-cloud https://mcp.clickhouse.cloud/mcp` for ClickHouse Cloud (OAuth, read-only, zero config), or self-hosted via `pip install mcp-clickhouse` with `CLICKHOUSE_HOST`/`USER`/`PASSWORD`/`SECURE` env vars (`CLICKHOUSE_ALLOW_WRITE_ACCESS=true` to enable writes). ~200–500ms overhead per call — fine for discovery/analysis, not for large batch operations.
- **CLI** (`clickhouse client`) or the **HTTP interface** (`curl` with `X-ClickHouse-User`/`Key` headers) for scripting, automation, or results >10K rows — zero per-call overhead.
- Always specify an output format — the default (TabSeparated, no headers) isn't agent-parseable. Use `JSON` by default; switch to `TabSeparatedWithNames` when result sets are large and token budget matters.
- ClickHouse Cloud services can be idle/sleeping — expect a 10–20s wake-up delay and a possible `503` on the first query after inactivity; retry once before treating it as a real error.

Source: adapted from [ClickHouse/agent-skills](https://github.com/ClickHouse/agent-skills) rules
`agent-discovery-schema`, `agent-query-safety`, `agent-connect-mcp` (Apache-2.0).
