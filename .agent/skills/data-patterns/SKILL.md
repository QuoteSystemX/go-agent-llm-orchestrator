---
name: data-patterns
description: Data engineering patterns — ETL/ELT pipeline design, dbt transformations, Airflow DAG authoring, Kafka streaming, data modeling (star/snowflake), ClickHouse/BigQuery analytics, data quality with Great Expectations, and PySpark. Universal — works in Antigravity (Gemini) and Claude Code.
version: 1.0.0
---

# Data Engineering Patterns Skill

> "Pipelines are code. Treat data contracts like API contracts." — Data Engineering Maxim

---

## 📐 PIPELINE DESIGN PRINCIPLES

### Batch vs Streaming Decision Tree

```
Data arrives...
│
├── Continuously (events, clicks, trades)
│   ├── Latency < 1s required?  → Kafka + Flink / ksqlDB
│   └── Latency 1s–5min OK?     → Kafka + Spark Structured Streaming
│
└── Periodically (nightly dumps, API pulls, DB exports)
    ├── < 100 GB/run?            → dbt + Airflow (SQL-first)
    └── > 100 GB/run?            → Spark + Airflow (distributed)
```

### Idempotency Rule (MANDATORY)

Every pipeline stage MUST be idempotent:

```sql
-- ✅ Safe re-run: INSERT OVERWRITE partition
INSERT OVERWRITE TABLE orders PARTITION (date = '2024-01-15')
SELECT * FROM raw_orders WHERE date = '2024-01-15';

-- ❌ Dangerous: appends duplicates on re-run
INSERT INTO orders SELECT * FROM raw_orders WHERE date = '2024-01-15';
```

---

## 🏗️ DATA MODELING

### Dimensional Modeling (Kimball)

```
Fact Tables          → Measurements, metrics, events (immutable rows)
Dimension Tables     → Descriptive context (slowly changing)
Bridge Tables        → Many-to-many relationships
```

```sql
-- Fact table: granularity = one row per trade
CREATE TABLE fact_trades (
    trade_id        BIGINT,
    trade_date_key  INT REFERENCES dim_date(date_key),
    symbol_key      INT REFERENCES dim_symbol(symbol_key),
    quantity        DECIMAL(18, 8),
    price           DECIMAL(18, 8),
    side            VARCHAR(4)  -- 'BUY' | 'SELL'
);

-- Dimension: slowly-changing Type 2
CREATE TABLE dim_symbol (
    symbol_key      SERIAL PRIMARY KEY,
    symbol          VARCHAR(20),
    exchange        VARCHAR(50),
    valid_from      DATE,
    valid_to        DATE,       -- NULL = current record
    is_current      BOOLEAN
);
```

### dbt Model Layers

```
sources/         → raw tables (no transformations)
staging/         → stg_*: 1-to-1 source mapping, type casting, renaming
intermediate/    → int_*: joins, business logic, not exposed to BI
marts/           → fct_* and dim_*: final analytics-ready tables
```

<!-- EMBED_END -->

---

## 🔧 DBT PATTERNS

### Model Configuration

```sql
-- models/marts/fct_trades.sql
{{
  config(
    materialized = 'incremental',
    unique_key    = 'trade_id',
    on_schema_change = 'sync_all_columns',
    partition_by  = {'field': 'trade_date', 'data_type': 'date'},
    cluster_by    = ['symbol']
  )
}}

SELECT
    t.trade_id,
    t.trade_date,
    s.symbol_key,
    t.quantity,
    t.price
FROM {{ ref('stg_raw_trades') }} t
LEFT JOIN {{ ref('dim_symbol') }} s ON t.symbol = s.symbol AND s.is_current

{% if is_incremental() %}
WHERE t.trade_date >= (SELECT MAX(trade_date) FROM {{ this }})
{% endif %}
```

### dbt Tests (data contracts)

```yaml
# models/marts/schema.yml
models:
  - name: fct_trades
    columns:
      - name: trade_id
        tests:
          - unique
          - not_null
      - name: price
        tests:
          - not_null
          - dbt_utils.accepted_range:
              min_value: 0
              inclusive: false
      - name: side
        tests:
          - accepted_values:
              values: ['BUY', 'SELL']
```

### Sources with Freshness

```yaml
# models/sources.yml
sources:
  - name: raw
    database: warehouse
    schema: raw
    freshness:
      warn_after: {count: 12, period: hour}
      error_after: {count: 24, period: hour}
    tables:
      - name: trades
        loaded_at_field: _loaded_at
```

---

## ⚙️ AIRFLOW DAG PATTERNS

### DAG Structure (TaskFlow API)

```python
from airflow.decorators import dag, task
from airflow.utils.dates import days_ago
from datetime import timedelta

default_args = {
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "email_on_failure": True,
}

@dag(
    schedule_interval="0 2 * * *",
    start_date=days_ago(1),
    catchup=False,
    default_args=default_args,
    tags=["trading", "daily"],
)
def trades_pipeline():

    @task()
    def extract() -> dict:
        # Pull from source, return metadata
        return {"rows": 1000, "source": "exchange_api"}

    @task()
    def transform(metadata: dict) -> dict:
        # dbt run --select stg_trades+
        return {**metadata, "transformed": True}

    @task()
    def load(metadata: dict) -> None:
        # Validate and publish
        assert metadata["rows"] > 0, "Empty extract — abort"

    load(transform(extract()))

dag = trades_pipeline()
```

### Idempotent Execution via Logical Date

```python
@task()
def extract(ds: str = None):
    # ds = logical date injected by Airflow (YYYY-MM-DD)
    # Re-running same date always produces same result
    return fetch_data(partition_date=ds)
```

---

## 📡 KAFKA STREAMING PATTERNS

### Producer (Python)

```python
from confluent_kafka import Producer
import json

producer = Producer({
    "bootstrap.servers": "kafka:9092",
    "acks": "all",           # Wait for all replicas
    "enable.idempotence": True,
    "compression.type": "lz4",
})

def delivery_report(err, msg):
    if err:
        raise RuntimeError(f"Delivery failed: {err}")

def publish_trade(trade: dict) -> None:
    producer.produce(
        topic="trades.raw",
        key=trade["symbol"].encode(),
        value=json.dumps(trade).encode(),
        callback=delivery_report,
    )
    producer.flush()
```

### Consumer (Python) with At-Least-Once

```python
from confluent_kafka import Consumer

consumer = Consumer({
    "bootstrap.servers": "kafka:9092",
    "group.id": "trades-processor",
    "auto.offset.reset": "earliest",
    "enable.auto.commit": False,  # Manual commit after processing
})

consumer.subscribe(["trades.raw"])

while True:
    msg = consumer.poll(timeout=1.0)
    if msg is None:
        continue
    if msg.error():
        handle_error(msg.error())
        continue

    process_trade(json.loads(msg.value()))
    consumer.commit(asynchronous=False)  # Commit only after success
```

### Topic Naming Convention

```
<domain>.<entity>.<version>
trades.raw.v1          → raw ingestion
trades.validated.v1    → after schema validation
trades.enriched.v1     → after symbol enrichment
trades.dead-letter.v1  → failed records for investigation
```

---

## 🗄️ CLICKHOUSE ANALYTICS PATTERNS

### Table Engine Selection

| Use Case | Engine | Why |
|----------|--------|-----|
| Append-only events/trades | `MergeTree` | High write throughput |
| Time-series with TTL | `MergeTree` + TTL | Auto-expire old partitions |
| Aggregated summaries | `AggregatingMergeTree` | Pre-aggregate on insert |
| Deduplication | `ReplacingMergeTree` | Last-write-wins by key |
| Distributed cluster | `Distributed` | Sharded reads/writes |

### MergeTree Best Practice

```sql
CREATE TABLE trades (
    trade_date  Date,
    symbol      LowCardinality(String),
    side        Enum8('BUY' = 1, 'SELL' = 2),
    quantity    Decimal(18, 8),
    price       Decimal(18, 8),
    created_at  DateTime64(3)
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(trade_date)
ORDER BY (symbol, trade_date, created_at)
SETTINGS index_granularity = 8192;
```

### Incremental Materialized View

```sql
CREATE MATERIALIZED VIEW trades_daily_mv
TO trades_daily
AS
SELECT
    trade_date,
    symbol,
    countMerge(cnt)  AS trades_count,
    sumMerge(volume) AS total_volume
FROM trades_daily_state
GROUP BY trade_date, symbol;
```

---

## ✅ DATA QUALITY CHECKLIST

### Pipeline Health

- [ ] Every stage is idempotent (safe re-run)
- [ ] Failed records route to dead-letter queue
- [ ] Schema validated at ingestion boundary
- [ ] SLA alert configured (freshness + row count)
- [ ] Data lineage documented (source → mart)

### dbt Quality

- [ ] `unique` + `not_null` on every primary key
- [ ] `accepted_values` on every enum column
- [ ] Source freshness configured with `warn_after` / `error_after`
- [ ] `dbt test` passes 100% before promoting to production

### Kafka Health

- [ ] Consumer lag monitored (alert if lag > threshold)
- [ ] Dead-letter topic exists and is monitored
- [ ] Schema registry used for Avro/Protobuf messages
- [ ] Retention policy set per topic (not default 7 days everywhere)

---

## Changelog

- **1.0.0** (2026-04-26): Initial version — ETL/ELT decision tree, dimensional modeling, dbt layers + incremental models, Airflow TaskFlow, Kafka producer/consumer, ClickHouse engines, data quality checklist
