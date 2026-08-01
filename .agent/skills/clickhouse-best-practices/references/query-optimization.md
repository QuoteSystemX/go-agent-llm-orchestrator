# Query Optimization — JOINs, Skip Indices, Materialized Views

## JOIN Algorithm (CRITICAL — default hash join loads the RIGHT table entirely into memory)

| Algorithm | Best for | Trade-off |
|---|---|---|
| `parallel_hash` | Small/medium in-memory tables | Default since 24.11; fast, concurrent |
| `hash` | General purpose | Single-threaded hash table build |
| `direct` | Dictionary lookups (INNER/LEFT only) | Fastest, no hash table |
| `full_sorting_merge` | Tables already sorted on join key | Skips sort if pre-ordered; low memory |
| `partial_merge` | Large × large, memory-constrained | Minimized memory, slower |
| `grace_hash` | Large datasets, tunable memory | Disk-spilling capability |
| `auto` | Default adaptive | Tries hash, falls back under memory pressure |

On 24.12+, ClickHouse auto-positions the smaller table on the right; on earlier versions, put the
smaller table on the RIGHT manually.

## Filter before joining (CRITICAL)

Joining full tables then filtering wastes resources — filter in subqueries first (or aggregate
before joining):

```sql
-- Filter each side down before the join, not after
SELECT o.order_id, c.name, o.total
FROM (SELECT order_id, customer_id, total FROM orders WHERE created_at > '2024-01-01') o
JOIN (SELECT id, name FROM customers WHERE country = 'US') c ON c.id = o.customer_id;
```

## ANY JOIN when only one match is needed (HIGH)

`LEFT ANY JOIN` / `INNER ANY JOIN` return at most one match — less memory, faster than a full JOIN
when you don't need every matching row.

## Data Skipping Indices (HIGH — apply *after* PK/types/MVs, not as a first optimization)

For filters on columns **not** in ORDER BY, which otherwise force a full scan:

```sql
ALTER TABLE events ADD INDEX idx_user_id user_id TYPE bloom_filter GRANULARITY 4;
ALTER TABLE events MATERIALIZE INDEX idx_user_id;
```

| Index type | Best for |
|---|---|
| `bloom_filter` | Equality on high-cardinality columns |
| `set(N)` | Low cardinality (N unique values) |
| `minmax` | Range queries |
| `ngrambf_v1` / `tokenbf_v1` | Text / token search |

Verify with `EXPLAIN indexes = 1 SELECT ...` — look for `Skip` entries showing granules skipped.
Don't reach for skip indices before checking PK design and materialized views first — they're a
targeted fix for specific non-key filters, not a general accelerator.

## Materialized Views (HIGH)

**Incremental MV** — applies the view query to new blocks at insert time, writes to a target
table. Use `-State` functions in the MV, `-Merge` in the query. Best for repeated real-time
aggregation over append-only data (reads thousands of rows instead of billions):

```sql
CREATE TABLE events_hourly (
    event_type LowCardinality(String), hour DateTime,
    events AggregateFunction(count), unique_users AggregateFunction(uniq, UInt64)
) ENGINE = AggregatingMergeTree() ORDER BY (event_type, hour);

CREATE MATERIALIZED VIEW events_hourly_mv TO events_hourly AS
SELECT event_type, toStartOfHour(timestamp) hour, countState() events, uniqState(user_id) unique_users
FROM events GROUP BY event_type, hour;
```

**Refreshable MV** — re-executes the full query on a schedule (`REFRESH EVERY 5 MINUTE`), best for
complex multi-table joins/denormalization where per-row incremental triggers don't fit. Query
should run fast relative to the refresh interval, or you'll fall behind.

Source: adapted from [ClickHouse/agent-skills](https://github.com/ClickHouse/agent-skills) rules
`query-join-*`, `query-index-skipping-indices`, `query-mv-*` (Apache-2.0).
