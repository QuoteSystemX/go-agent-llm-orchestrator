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

### 1. log_event (Python Script)
Record a metric event using the provided script.

**Usage**:
```bash
python3 .agent/skills/telemetry/scripts/log_event.py \
  --agent "frontend-specialist" \
  --metric "latency_ms" \
  --value "4500" \
  --meta '{"model": "gemini-1.5-pro", "step": "layout-gen"}'
```

**Metric Types**:
- `prompt_tokens`: Number of tokens in the request.
- `completion_tokens`: Number of tokens in the response.
- `latency_ms`: Time taken for the action.
- `cache_hit`: Boolean (1 or 0) for caching status.
- `status`: Execution status (`success`, `fail`, `retry`).

## Dashboard & Analysis

Data from `metrics.jsonl` can be analyzed using:
1. `.agent/scripts/misc/metrics_dashboard.py` (Visual representation)
2. `.agent/scripts/knowledge/experience_distiller.py` (Historical patterns)

## Best Practices

1. **Non-blocking**: Logging should be fast. Use the CLI tool asynchronously if possible.
2. **Granularity**: Log both successful completions and errors/retries.
3. **Consistency**: Use standardized metric names as listed above.

---

## Implementation Details (Python API)

You can also import the logger directly in other scripts:

```python
from .agent.skills.telemetry.scripts.log_event import log_event

log_event(
    agent="my-agent",
    metric="custom_stat",
    value=100,
    metadata={"env": "prod"}
)
```

## Changelog

- **1.1.0** (2026-05-12): Added `log_event.py` script and CLI interface.
- **1.0.0** (2026-05-07): Initial version

