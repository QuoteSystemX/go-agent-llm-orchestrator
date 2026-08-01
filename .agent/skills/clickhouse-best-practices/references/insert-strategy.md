# Insert Strategy — Batching, Mutations, Optimize

## Batch size (CRITICAL)

Every `INSERT` creates a new data part. Single-row or tiny-batch inserts create thousands of
parts and overwhelm the background merge process, eventually blocking further inserts.

| Threshold | Value |
|---|---|
| Minimum | 1,000 rows |
| Ideal range | 10,000–100,000 rows |
| Sync insert rate | ~1 insert/second |

Monitor: `SELECT table, count() parts, sum(rows) FROM system.parts WHERE active GROUP BY table` —
more than ~3,000 parts per partition starts blocking inserts.

## Async inserts (HIGH) — when client-side batching isn't practical

```sql
SET async_insert = 1;
SET wait_for_async_insert = 1;   -- confirms durability; the recommended mode
```

Server buffers small writes and flushes on `async_insert_max_data_size` or
`async_insert_busy_timeout_ms`, whichever comes first. `wait_for_async_insert=0` is fire-and-forget
and risks silent data loss — only use it if that's acceptable.

## Avoid `ALTER TABLE UPDATE`/`DELETE` (CRITICAL)

These are mutations: they rewrite entire affected parts, spike disk I/O, can't be rolled back, and
`SELECT` may read a mix of mutated/unmutated parts mid-mutation.

**Updates** → `ReplacingMergeTree`: "update" by inserting a new version, query with `FINAL` or
`argMax()`:

```sql
CREATE TABLE users (user_id UInt64, name String, status LowCardinality(String), updated_at DateTime DEFAULT now())
ENGINE = ReplacingMergeTree(updated_at) ORDER BY user_id;

INSERT INTO users (user_id, name, status) VALUES (123, 'John', 'inactive');
SELECT * FROM users FINAL WHERE user_id = 123;
```

**Deletes** → `CollapsingMergeTree` (sign column, insert `-1` row to cancel) or lightweight
`DELETE FROM ... WHERE ...` (23.3+, marks rows, physically removed on next merge) or
`ALTER TABLE ... DROP PARTITION` for instant bulk deletion by partition — much faster than a
`DELETE WHERE` scan.

Reserve `ALTER TABLE UPDATE/DELETE` for rare, one-off corrections only.

## Avoid `OPTIMIZE TABLE ... FINAL` (HIGH)

Forces an expensive full merge of all parts in a partition. Background merges already handle this
automatically. If you need deduplicated `ReplacingMergeTree` reads, use the `FINAL` *modifier in a
SELECT* (cheap, scoped) rather than running `OPTIMIZE ... FINAL` (expensive, whole-partition) after
every insert.

## Insert format (MEDIUM)

Native format is fastest (column-oriented, minimal parsing) > RowBinary > JSONEachRow (easiest to
use, most parsing overhead).

Source: adapted from [ClickHouse/agent-skills](https://github.com/ClickHouse/agent-skills) rules
`insert-batch-size`, `insert-async-small-batches`, `insert-mutation-avoid-*`,
`insert-optimize-avoid-final`, `insert-format-native` (Apache-2.0).
