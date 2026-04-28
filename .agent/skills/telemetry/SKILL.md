---
name: telemetry
description: Record agent execution metrics (tokens, latency, status) for real-time monitoring and AI analysis.
version: 1.0.0
---

# Telemetry & Live Metrics

**Purpose**: Capture granular performance data for every agent action.

## Core Principle

> **Measure everything to optimize everything.**

## Storage

- **Log File**: `.agent/logs/metrics.jsonl` (Append-only JSON Lines)

## Tools & Usage

### 1. log_event
Log a metric event.

**Fields**:
- `ts`: ISO timestamp
- `agent`: Name of the agent
- `metric`: Type of metric (`prompt_tokens`, `completion_tokens`, `latency_ms`, `status`)
- `value`: Numeric or string value
- `session_id`: UUID for the current session (optional)

**Example**:
```javascript
log_event({
  agent: "backend-specialist",
  metric: "latency_ms",
  value: 4500,
  metadata: { model: "gemini-1.5-pro" }
});
```

## Dashboard integration

Data from `metrics.jsonl` is consumed by `.agent/scripts/metrics_dashboard.py`.

## Best Practices

1. **Non-blocking**: Logging should be extremely fast (simple file append).
2. **Granularity**: Log both successful completions and errors/retries.
3. **Consistency**: Use standardized metric names.

---

## Implementation Details (Python)

```python
import json
from datetime import datetime, timezone

def log_event(data):
    data["ts"] = datetime.now(timezone.utc).isoformat()
    with open(".agent/logs/metrics.jsonl", "a") as f:
        f.write(json.dumps(data) + "\n")
```
