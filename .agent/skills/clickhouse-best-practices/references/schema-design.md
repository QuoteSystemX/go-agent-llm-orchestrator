# Schema Design — Primary Key, Types, Partitioning, JSON

## Primary Key / ORDER BY (CRITICAL — plan before `CREATE TABLE`)

`ORDER BY` defines physical row ordering and the sparse index. **It cannot be modified after
creation** — a wrong choice means creating a new table and migrating all data.

**Before creating a table:** list your top 5–10 query patterns, identify which WHERE columns
exclude the most rows, order columns low-to-high cardinality, and limit to 4–5 key columns.

```sql
-- Query analysis first: 60% filter user_id+timestamp, 25% event_type+timestamp
CREATE TABLE events (
    event_id UUID DEFAULT generateUUIDv4(),
    user_id UInt64,
    event_type LowCardinality(String),
    timestamp DateTime,
    event_date Date DEFAULT toDate(timestamp)
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(event_date)
ORDER BY (user_id, event_date, event_id);   -- low-to-high cardinality, filter columns first
```

- **Cardinality order**: low-cardinality columns first (they let the index skip whole granules),
  high-cardinality (UUIDs) last. `ORDER BY (event_id, event_type, timestamp)` gives zero pruning
  benefit; `ORDER BY (event_type, event_date, event_id)` does.
- **Prioritize filter columns**: whatever's most frequently in `WHERE` goes first, or you get a
  full table scan on that query.
- **Queries must use the ORDER BY prefix.** `WHERE tenant_id = 123` uses the index if `tenant_id`
  is first in ORDER BY; `WHERE event_type = 'click'` (skipping the prefix) does not — verify with
  `EXPLAIN indexes = 1 SELECT ...` and look for `PrimaryKey` with a Key Condition.

## Data Types (CRITICAL/HIGH)

Use native types, not `String` for everything — 2–10x storage reduction and correct semantics.

| Data | Use | Avoid |
|---|---|---|
| Sequential IDs | UInt32/UInt64 | String |
| UUIDs | UUID (16B) | String (36B) |
| Status/category | Enum8/16 or LowCardinality(String) | String |
| Timestamps | DateTime | String |
| Dates only | Date/Date32 | DateTime, String |
| Counts | smallest UInt that fits | Int64, String |
| Money | Decimal(P,S) or Int64 (cents) | Float64, String |
| Booleans | Bool/UInt8 | String |

- **Minimize bit-width**: `age UInt8`, `status_code UInt16`, not everything `Int64`.
- **LowCardinality(String)** for columns with <10K unique values (country, browser, event_type) —
  dictionary-encodes them. Check with `SELECT uniq(col) FROM table`. Above 10K uniques, use plain
  `String`. Reserve `FixedString(N)` for genuinely fixed-length data (e.g. 2-char country codes).
- **Avoid `Nullable` unless NULL is semantically meaningful.** `Nullable` adds a hidden UInt8
  tracking column per row. Use `DEFAULT 0` / `DEFAULT ''` instead — reserve `Nullable` for cases
  like `deleted_at` (NULL = not deleted) or `parent_id` (NULL = no parent) where NULL *means*
  something distinct from a default value.
- **Enum8/16** for finite known value sets — gives insert-time validation (`INSERT ... 'shiped'`
  rejected) and natural ordering without CASE statements. Use `LowCardinality(String)` instead if
  the value set changes frequently.

## Partitioning (HIGH — a lifecycle tool, not a query-optimization tool)

Partitioning's job is dropping/archiving data cheaply, not speeding up queries — that's ORDER BY's
job.

```sql
CREATE TABLE events (timestamp DateTime, event_type LowCardinality(String))
ENGINE = MergeTree()
PARTITION BY toStartOfMonth(timestamp)   -- bounded: 12/year
ORDER BY (event_type, timestamp)
TTL timestamp + INTERVAL 1 YEAR DELETE;  -- drops whole partitions, metadata-only

ALTER TABLE events DROP PARTITION '202301';  -- instant, vs DELETE WHERE (row-by-row scan)
```

- **Keep partition cardinality bounded (100–1,000 values).** `PARTITION BY user_id` or
  `PARTITION BY toDate(timestamp)` over years of data can blow past `max_parts_in_total` and start
  throwing "too many parts" errors. Prefer `toStartOfMonth`/`toYYYYMM` over raw daily partitioning
  unless retention is genuinely day-scale.
- If unsure, **start without partitioning** — it's easy to add later and premature fine-grained
  partitioning is a common source of part explosion.
- Check health: `SELECT partition, count() parts, sum(rows) FROM system.parts WHERE table = 'x' AND active GROUP BY partition` — hundreds/thousands of partitions is a warning sign.

## JSON columns (MEDIUM)

Use ClickHouse's `JSON` type only for genuinely dynamic/variable schemas (splits into queryable
sub-columns with type inference). For a fixed known schema, use typed columns. For an opaque blob
never queried by field, plain `String` is fine — `JSON` buys nothing there.

```sql
CREATE TABLE events (
    event_type LowCardinality(String),
    properties JSON   -- or JSON(url String, amount Float64) to pin known paths
) ENGINE = MergeTree() ORDER BY (event_type, timestamp);

SELECT properties.url, properties.amount FROM events WHERE event_type = 'purchase';
```

Source: adapted from [ClickHouse/agent-skills](https://github.com/ClickHouse/agent-skills) rules
`schema-pk-*`, `schema-types-*`, `schema-partition-*`, `schema-json-when-to-use` (Apache-2.0).
