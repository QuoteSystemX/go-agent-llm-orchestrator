---
name: observability-patterns
description: Production observability — OpenTelemetry instrumentation, Prometheus + Grafana (ServiceMonitor, recording rules, alerting), structured logging (logrus → Loki), distributed tracing (Jaeger/Tempo), SLO/SLI/SLA definitions, error budget, Alertmanager routing, on-call runbooks. Universal — works in Antigravity (Gemini) and Claude Code.
version: 1.0.0
---

# Observability Patterns Skill

> You cannot fix what you cannot see.
> **Observability = Metrics + Logs + Traces, always correlated.**

---

## 1. The Three Pillars

| Pillar | Tool | What it answers |
| ------ | ---- | --------------- |
| **Metrics** | Prometheus + Grafana | Is my system healthy? How fast? |
| **Logs** | slog → Loki → Grafana | Why did it fail? What happened? |
| **Traces** | OpenTelemetry → Jaeger/Tempo | Where is the bottleneck across services? |

Implement all three — each answers different questions. Logs without traces are blind in microservices; metrics without logs hide the root cause.

---

## 2. OpenTelemetry Instrumentation

### Go service — SDK setup

```go
// telemetry/setup.go
package telemetry

import (
    "context"
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp"
    "go.opentelemetry.io/otel/sdk/resource"
    sdktrace "go.opentelemetry.io/otel/sdk/trace"
    semconv "go.opentelemetry.io/otel/semconv/v1.21.0"
)

func InitTracer(ctx context.Context, serviceName, version string) (func(), error) {
    exp, err := otlptracehttp.New(ctx)
    if err != nil {
        return nil, fmt.Errorf("create OTLP exporter: %w", err)
    }

    res := resource.NewWithAttributes(
        semconv.SchemaURL,
        semconv.ServiceName(serviceName),
        semconv.ServiceVersion(version),
    )

    tp := sdktrace.NewTracerProvider(
        sdktrace.WithBatcher(exp),
        sdktrace.WithResource(res),
        sdktrace.WithSampler(sdktrace.ParentBased(sdktrace.TraceIDRatioBased(0.1))),
    )
    otel.SetTracerProvider(tp)

    return func() { tp.Shutdown(context.Background()) }, nil
}
```

### Span naming conventions

```go
// Pattern: <verb> <noun> — lowercase, no IDs
tracer := otel.Tracer("payment-service")

ctx, span := tracer.Start(ctx, "process payment")
defer span.End()

// Add attributes — structured, not string-interpolated
span.SetAttributes(
    attribute.String("payment.method", method),
    attribute.Int64("payment.amount_cents", amount),
)

// Record errors
if err != nil {
    span.RecordError(err)
    span.SetStatus(codes.Error, err.Error())
    return err
}
```

### HTTP middleware — auto-instrument

```go
import "go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"

// Wrap router
mux := http.NewServeMux()
handler := otelhttp.NewHandler(mux, "api-server",
    otelhttp.WithSpanNameFormatter(func(_ string, r *http.Request) string {
        return r.Method + " " + r.URL.Path
    }),
)
```

---

## 3. Prometheus Metrics

### Metric types — choose correctly

| Type | Use when | Example |
|------|----------|---------|
| `Counter` | Monotonically increasing | requests_total, errors_total |
| `Gauge` | Value goes up and down | active_connections, queue_depth |
| `Histogram` | Distribution of values | request_duration_seconds |
| `Summary` | Pre-computed quantiles (avoid in federation) | — |

### Standard service metrics (RED method)

```go
var (
    requestsTotal = prometheus.NewCounterVec(
        prometheus.CounterOpts{
            Name: "http_requests_total",
            Help: "Total HTTP requests by method, path, and status.",
        },
        []string{"method", "path", "status"},
    )

    requestDuration = prometheus.NewHistogramVec(
        prometheus.HistogramOpts{
            Name:    "http_request_duration_seconds",
            Help:    "HTTP request latency.",
            Buckets: prometheus.DefBuckets, // .005,.01,.025,.05,.1,.25,.5,1,2.5,5,10
        },
        []string{"method", "path"},
    )
)

func init() {
    prometheus.MustRegister(requestsTotal, requestDuration)
}
```

### Kubernetes: ServiceMonitor (Prometheus Operator)

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: payment-service
  namespace: monitoring
spec:
  selector:
    matchLabels:
      app: payment-service
  endpoints:
    - port: metrics
      interval: 15s
      path: /metrics
```

### Recording rules — pre-compute expensive queries

```yaml
# prometheus/rules/payment.yml
groups:
  - name: payment.rules
    interval: 1m
    rules:
      - record: job:http_requests:rate5m
        expr: rate(http_requests_total[5m])

      - record: job:http_error_rate:rate5m
        expr: |
          rate(http_requests_total{status=~"5.."}[5m])
          /
          rate(http_requests_total[5m])
```

---

## 4. Structured Logging (slog / zap)

### Setup — always structured, never fmt.Sprintf in log messages

```go
import "log/slog"

func NewLogger(service, version string) *slog.Logger {
    handler := slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
        Level: slog.LevelInfo,
        ReplaceAttr: func(groups []string, a slog.Attr) slog.Attr {
            // Standardize timestamp
            if a.Key == slog.TimeKey {
                a.Value = slog.StringValue(a.Value.Time().Format(time.RFC3339Nano))
            }
            return a
        },
    })
    
    return slog.New(handler).With(
        slog.String("service", service),
        slog.String("version", version),
    )
}
```

### Field conventions

```go
// ✅ Structured — Loki can index and filter
logger.InfoContext(ctx, "order processed",
    slog.String("user_id", userID),
    slog.String("order_id", orderID),
    slog.Int64("amount", amount),
    slog.Duration("duration", time.Since(start)),
)

// 🚫 Unstructured — Loki can only grep
logger.Info(fmt.Sprintf("order %s processed for user %s", orderID, userID))
```

### Log levels — use consistently

| Level | When |
|-------|------|
| `Debug` | Dev only, disabled in prod |
| `Info` | Normal business events (order placed, user logged in) |
| `Warn` | Expected errors, degraded mode (retry #3, circuit open) |
| `Error` | Unexpected failures that need attention |
| `Fatal` | Initialization failures — process exits |

### Loki label strategy

```yaml
# promtail config — label only low-cardinality fields
pipeline_stages:
  - json:
      expressions:
        level: level
        service: service
  - labels:
      level:    # ✅ low cardinality
      service:  # ✅ low cardinality
  # ❌ NEVER label: user_id, order_id, trace_id — too many series
```

---

## 5. Distributed Tracing (Jaeger / Tempo)

### Trace → Log correlation

Always inject trace ID into log context using `slog`:

```go
func (h *TraceHandler) Handle(ctx context.Context, r slog.Record) error {
    span := trace.SpanFromContext(ctx)
    if span.IsRecording() {
        sc := span.SpanContext()
        r.AddAttrs(
            slog.String("trace_id", sc.TraceID().String()),
            slog.String("span_id", sc.SpanID().String()),
        )
    }
    return h.next.Handle(ctx, r)
}

// Usage:
logger.InfoContext(ctx, "processing order", slog.String("user_id", id))
```

In Grafana: click a log line → jump directly to the trace. This is the key value of correlation.

### Sampling strategy

```go
// Production: head-based, 10% of traffic
sdktrace.WithSampler(sdktrace.ParentBased(
    sdktrace.TraceIDRatioBased(0.1),
))

// Always sample errors (tail-based, needs collector)
// Use OpenTelemetry Collector + tail_sampling processor
```

---

## 6. SLO / SLI / SLA Definitions

### Vocabulary

| Term | Definition | Owner |
|------|-----------|-------|
| **SLI** (Indicator) | Measurable metric: `success_rate = ok_requests / total_requests` | Engineering |
| **SLO** (Objective) | Target: SLI ≥ 99.9% over 30 days | Engineering + Product |
| **SLA** (Agreement) | Contract with penalty: SLO violated → credit | Legal + Business |
| **Error Budget** | `(1 - SLO) × window` = 43.8 min/month for 99.9% | Engineering |

### Standard SLI query pattern (Prometheus)

```yaml
# Availability SLI
- record: sli:availability:ratio_rate5m
  expr: |
    sum(rate(http_requests_total{status!~"5.."}[5m]))
    /
    sum(rate(http_requests_total[5m]))

# Latency SLI — % requests under 300ms
- record: sli:latency_p99:ratio_rate5m
  expr: |
    histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))
```

### Error budget burn rate alert

```yaml
# Alert when burning 5% of monthly budget in 1 hour
- alert: ErrorBudgetBurnHigh
  expr: |
    (
      1 - sli:availability:ratio_rate5m
    ) > (5 * (1 - 0.999))
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "Error budget burning fast: {{ $value | humanizePercentage }} error rate"
    runbook: "https://wiki/runbooks/error-budget-burn"
```

---

## 7. Alertmanager Routing

### Routing tree pattern

```yaml
# alertmanager.yml
route:
  receiver: default
  group_by: [alertname, cluster]
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h

  routes:
    - matchers: [severity="critical"]
      receiver: pagerduty
      continue: false

    - matchers: [severity="warning"]
      receiver: slack-warnings
      group_wait: 5m

    - matchers: [team="data"]
      receiver: data-team-slack

receivers:
  - name: pagerduty
    pagerduty_configs:
      - routing_key: ${PAGERDUTY_KEY}

  - name: slack-warnings
    slack_configs:
      - channel: "#alerts-warning"
        text: "{{ range .Alerts }}{{ .Annotations.summary }}\n{{ end }}"
```

### Alert labels — required on every alert

```yaml
labels:
  severity: critical | warning | info
  team: backend | data | platform
  service: payment-service
annotations:
  summary: "Human-readable one-liner"
  description: "More detail with {{ $value }}"
  runbook: "https://wiki/runbooks/<name>"  # mandatory for critical
```

---

## 8. On-Call Runbook Template

Every `critical` alert MUST have a runbook. Minimal structure:

```markdown
# Runbook: <AlertName>

## What is firing
One sentence: what the alert means in business terms.

## Impact
- Who is affected (users / internal / none visible)
- SLO impact: burning X% of error budget

## Diagnosis (ordered by likelihood)
1. Check dashboard: [link] → look for Y
2. `kubectl logs -n prod deploy/<svc> --tail=100 | grep ERROR`
3. Check upstream dependency: [service]

## Mitigation
- **Quick fix (< 5 min):** `kubectl rollout restart deploy/<svc>`
- **Escalation:** If not resolved in 15 min → page @backend-lead

## Root cause categories
- [ ] Dependency failure
- [ ] Config change
- [ ] Traffic spike
- [ ] Code regression

## Post-mortem
Link to post-mortem after resolution.
```

---

## 9. Grafana Dashboard Conventions

```json
{
  "title": "<Service> — Overview",
  "tags": ["service", "slo", "RED"],
  "panels": [
    { "title": "Request Rate",    "type": "timeseries", "expr": "rate(http_requests_total[5m])" },
    { "title": "Error Rate %",    "type": "stat",       "expr": "sli:error_rate:ratio_rate5m * 100" },
    { "title": "p99 Latency",     "type": "timeseries", "expr": "histogram_quantile(0.99, rate(...))" },
    { "title": "SLO Burn Rate",   "type": "gauge",      "thresholds": [{"color":"green","value":0},{"color":"red","value":1}] }
  ]
}
```

**Naming rules:** `<Service> — <Purpose>` (em dash, not hyphen). Tag with `slo` if it contains SLI panels. Keep RED metrics (Rate, Errors, Duration) in the first row of every service dashboard.

---

## 10. Common Pitfalls

| Pitfall | Fix |
|---------|-----|
| High-cardinality labels in Prometheus | Never label `user_id`, `order_id` → use trace attributes instead |
| Logging inside hot loop | Sample or aggregate, not per-iteration |
| Alert without runbook | Mandate `runbook:` annotation for `critical` |
| SLO defined only on availability | Also define latency SLI — a slow response is a failure |
| Sampling = 100% in prod | CPU/storage cost — use 10% + tail-sampling for errors |
| Traces without baggage propagation | Always propagate `traceparent` header across HTTP/gRPC calls |
| Using individual agents for collection | **Use Grafana Alloy** for unified collection of metrics, logs, and traces |

---

## 🛰️ Unified Telemetry (Grafana Alloy)

In 2026, **Grafana Alloy** is the standard collector. It replaces Promtail, Otel Collector, and Agent.
- **Pattern**: `otel.exporter.otlp` → `alloy` → `loki.write`, `prometheus.remote_write`, `tempo.write`.

## Changelog

- **1.0.0** (2026-05-07): Initial version
