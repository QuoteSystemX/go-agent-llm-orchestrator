---
name: grafana-dashboard-master
description: Expert-level Grafana dashboard design and engineering. Deep knowledge of Dashboard JSON schema, PromQL/LogQL optimization, advanced visualizations, and API-driven automation.
version: 1.0.0
---

# Grafana Dashboard Master Skill

> **"Data is the message, but Visualization is the language."**
> This skill enables the creation of high-performance, aesthetically pleasing, and insightful dashboards.

---

## 1. Core Visualization Principles

### The RED Method (Services)
For every microservice/API, the first row must contain:
1.  **Rate**: `sum(rate(http_requests_total[5m]))` - Throughput.
2.  **Errors**: `sum(rate(http_requests_total{status=~"5.."}[5m]))` - Failure rate.
3.  **Duration**: `histogram_quantile(0.99, sum by (le) (rate(http_request_duration_seconds_bucket[5m])))` - Latency.

### The USE Method (Resources)
For infra/hardware (CPU, RAM, Disk):
1.  **Utilization**: Average time resource was busy.
2.  **Saturation**: Degree to which extra work is queued.
3.  **Errors**: Count of error events.

---

## 2. Grafana JSON Schema Mastery

### Panel Layout & Grid Pos
Grafana uses a 24-column grid.
- **Small Stat**: `w: 4, h: 4`
- **Main Graph**: `w: 12, h: 8`
- **Row**: `w: 24, h: 1`

### Template Variables
Always parameterize dashboards for scalability:
```json
{
  "name": "service",
  "type": "query",
  "query": "label_values(http_requests_total, service)",
  "multi": true,
  "includeAll": true
}
```

---

## 3. Query Optimization (PromQL/LogQL)

- **Avoid High Cardinality**: Don't group by `user_id` or `trace_id` in Prometheus.
- **Recording Rules**: Use pre-computed metrics for heavy dashboards.
- **LogQL Filtering**: Filter by labels first `{service="api"}` before using line filters `|= "error"`.

---

## 4. Visual Excellence (HSL Sync)

- **Harmony**: Match colors with `visual-designer` design system.
- **Thresholds**:
  - `OK` (Green): Base state.
  - `Warning` (Yellow): SLO at risk.
  - `Critical` (Red): SLO violated.
- **Units**: Always set correct units (`ms`, `bytes`, `percent`) to avoid "1000ms" showing as "1s" incorrectly or vice versa.

---

## 5. Automation via API

Use `python3 .agent/scripts/health/grafana_manager.py` for:
- **Snapshotting**: Back up a dashboard before major edits.
- **Validation**: Check if a dashboard JSON is valid before push.
- **Discovery**: Search for existing dashboards to avoid duplication.

---
## 6. Template Engineering

Instead of manual JSON, use a "Factory" approach:
1.  **Row Factory**: Creates a row with a standard set of RED panels.
2.  **Alert Factory**: Generates alert rules based on SLO thresholds.
3.  **Variable Factory**: Standard cluster/namespace/service selectors.

## 7. Advanced Transformations

Use Grafana's internal transformation engine to:
- **Join by field**: Combine metrics from different sources (e.g. Prometheus + SQL).
- **Group by**: Aggregate data in the browser for small datasets.
- **Filter by value**: Hide "dead" series that return only zeros.

## 8. Implementation Workflow (Full Power)

1.  **Discovery**: Run `grafana_manager.py explore --ds-id <ID>` to see real metrics.
2.  **Variable Design**: Create `$service` variable based on `label_values`.
3.  **JSON Generation**: Use a template-first approach.
4.  **Dry Run**: Validate JSON structure.
5.  **Deployment**: Push via API.
6.  **Alerting**: Create companion alert rules via `grafana_manager.py alerts`.

## 9. Common Pitfalls

- **Hardcoded Datasources**: Use `-- Mixed --` or template variables for datasources.
- **Missing Units**: Numbers without context are meaningless.
- **Dashboard Bloat**: Too many panels (>20) make the browser slow. Use `Rows` to collapse content.

## Changelog

- **1.0.0** (2026-05-07): Initial version

## When to Use

- **Designing a new dashboard** for a service or resource — start
  with RED (Rate, Errors, Duration) for services, USE (Utilization,
  Saturation, Errors) for resources.
- **Optimizing slow dashboards** — check for unfiltered series,
  high-cardinality labels, missing time ranges.
- **API-driven deployment** — use `grafana_manager.py` to push
  dashboards as code (version-controlled, reviewable).
- **Alert design** — pair dashboards with companion alert rules.
- **Template variables** — use `label_values(...)` to make
  dashboards interactive without hardcoding.

Avoid using this skill for:
- Simple one-off charts (use `quickchart` or a notebook).
- Non-Prometheus datasources (this skill is PromQL/LogQL-focused).
- Backend logic (Grafana is a viewer, not a compute engine).

## Anti-Patterns

- **Don't use `*` in queries** — it pulls all series. Always use a
  specific label matcher (`{service="auth"}`).
- **Don't put a 30-day range on a high-cardinality panel** — the
  browser will hang. Use 1h or 6h for detailed panels.
- **Don't use `instant: true` for cumulative metrics** — you get
  a misleading flat line. Use `rate()` or `increase()`.
- **Don't hardcode datasource UIDs** — they change between
  environments. Use template variables.
- **Don't use `$__interval` in alert queries** — alerts need
  fixed intervals for consistency. Use `5m` or `1h` directly.
- **Don't mix timezones in panel titles** — show the timezone
  explicitly to avoid confusion.
- **Don't use gauges for "current value" without context** — a
  number without a sparkline or trend is meaningless.
- **Don't use Stat panels for trends** — they show current value
  only. Use Time series with sparkline.
