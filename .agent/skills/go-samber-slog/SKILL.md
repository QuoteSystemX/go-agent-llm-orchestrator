---
name: go-samber-slog
description: Structured logging extensions for Go using samber/slog-**** packages — multi-handler pipelines (slog-multi), log sampling (slog-sampling), attribute formatting (slog-formatter), HTTP middleware (slog-fiber, slog-gin, slog-chi, slog-echo), and backend routing (slog-datadog, slog-sentry, slog-loki, slog-syslog, slog-logstash, slog-graylog...). Apply when using or adopting slog, or when the codebase already imports any github.com/samber/slog-* package.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
version: 1.0.0
source: Adapted from samber/cc-skills-golang@golang-samber-slog (MIT License) — https://github.com/samber/cc-skills-golang
---

# samber/slog-**** — Structured Logging Pipeline for Go

20+ composable `slog.Handler` packages for Go 1.21+, all implementing the standard `slog.Handler` interface.

**Official resources:** [slog-multi](https://github.com/samber/slog-multi) (composition) · [slog-sampling](https://github.com/samber/slog-sampling) (throughput control) · [slog-formatter](https://github.com/samber/slog-formatter) (attribute transformation)

## The Pipeline Model

Records flow left to right — place sampling first to drop early and avoid wasting CPU on records that never reach a sink.

```
record → [Sampling] → [Pipe: trace/PII] → [Router] → [Sinks]
```

Order matters: sampling before formatting saves CPU. Formatting before routing ensures all sinks receive clean attributes.

## Core Libraries

| Library | Purpose | Key constructors |
| --- | --- | --- |
| `slog-multi` | Handler composition | `Fanout`, `Router`, `FirstMatch`, `Failover`, `Pool`, `Pipe` |
| `slog-sampling` | Throughput control | `UniformSamplingOption`, `ThresholdSamplingOption`, `AbsoluteSamplingOption`, `CustomSamplingOption` |
| `slog-formatter` | Attribute transforms | `PIIFormatter`, `ErrorFormatter`, `FormatByType[T]`, `FormatByKey` |

## slog-multi — Handler Composition

| Pattern | Behavior | Latency impact |
| --- | --- | --- |
| `Fanout(handlers...)` | Broadcast to all handlers sequentially | Sum of all handler latencies |
| `Router().Add(h, predicate).Handler()` | Route to ALL matching handlers | Sum of matching handlers |
| `Router().Add(...).FirstMatch().Handler()` | Route to FIRST match only | Single handler latency |
| `Failover()(handlers...)` | Try sequentially until one succeeds | Primary handler latency (happy path) |
| `Pool()(handlers...)` | Load-balance: each record to ONE handler | Single handler latency |
| `Pipe(middlewares...).Handler(sink)` | Middleware chain before sink | Middleware overhead + sink |

```go
// Route errors to Sentry, all logs to stdout
logger := slog.New(
    slogmulti.Router().
        Add(sentryHandler, slogmulti.LevelIs(slog.LevelError)).
        Add(slog.NewJSONHandler(os.Stdout, nil)).
        Handler(),
)
```

Built-in predicates: `LevelIs`, `LevelIsNot`, `MessageIs`, `MessageContains`, `AttrValueIs`, `AttrKindIs`.

## slog-sampling — Throughput Control

| Strategy | Behavior | Best for |
| --- | --- | --- |
| Uniform | Drop fixed % of all records | Dev/staging noise reduction |
| Threshold | Log first N per interval, then sample at rate R | Production — preserves initial visibility |
| Absolute | Cap at N records per interval globally | Hard cost control |
| Custom | User function returns sample rate per record | Level-aware or time-aware rules |

Sampling MUST be the outermost handler in the pipeline.

```go
logger := slog.New(
    slogmulti.
        Pipe(slogsampling.ThresholdSamplingOption{
            Tick: 5 * time.Second, Threshold: 10, Rate: 0.1,
        }.NewMiddleware()).
        Handler(innerHandler),
)
```

## slog-formatter — Attribute Transformation

```go
logger := slog.New(
    slogmulti.Pipe(slogformatter.NewFormatterMiddleware(
        slogformatter.PIIFormatter("user"),
        slogformatter.ErrorFormatter("error"),
        slogformatter.IPAddressFormatter("client"),
    )).Handler(slog.NewJSONHandler(os.Stdout, nil)),
)
```

Key formatters: `PIIFormatter`, `ErrorFormatter`, `TimeFormatter`, `IPAddressFormatter`, `HTTPRequestFormatter`, `HTTPResponseFormatter`. Generic: `FormatByType[T]`, `FormatByKey`, `FormatByKind`, `FormatByGroup`.

## HTTP Middlewares

Consistent pattern across frameworks: `router.Use(slogXXX.New(logger))`. Available: `slog-gin`, `slog-echo`, `slog-fiber`, `slog-chi`, `slog-http`.

```go
router.Use(sloggin.NewWithConfig(logger, sloggin.Config{
    DefaultLevel:     slog.LevelInfo,
    ClientErrorLevel: slog.LevelWarn,
    ServerErrorLevel: slog.LevelError,
    WithRequestBody:  true,
    Filters: []sloggin.Filter{sloggin.IgnorePath("/health", "/metrics")},
}))
```

## Backend Sinks

| Category | Packages |
| --- | --- |
| Cloud | `slog-datadog`, `slog-sentry`, `slog-loki`, `slog-graylog` |
| Messaging | `slog-kafka`, `slog-fluentd`, `slog-logstash`, `slog-nats` |
| Notification | `slog-slack`, `slog-telegram`, `slog-webhook` |
| Bridges | `slog-zap`, `slog-zerolog`, `slog-logrus` |

**Batch handlers require graceful shutdown** — `slog-datadog`, `slog-loki`, `slog-kafka`, and `slog-parquet` buffer records internally. Flush on shutdown (`handler.Stop(ctx)`, `lokiClient.Stop()`, `writer.Close()`) or buffered logs are lost.

## Common Mistakes

| Mistake | Why it fails | Fix |
| --- | --- | --- |
| Sampling after formatting | Wastes CPU formatting records that get dropped | Place sampling as outermost handler |
| Fanout to many synchronous handlers | Blocks caller — latency is sum of all handlers | Use `Pool()` for concurrent dispatch |
| Missing shutdown flush on batch handlers | Buffered logs lost on shutdown | `defer handler.Stop(ctx)` etc. |
| Router without default/catch-all handler | Unmatched records silently dropped | Add a handler with no predicate as catch-all |

## Performance Warnings

- **Fanout latency** = sum of all handler latencies. Use `Pool()` to reduce to max(latencies)
- **Pipe middleware** adds per-record overhead — keep chains short (2-4 middlewares)
- Benchmark your pipeline with `go test -bench` before production deployment

## Best Practices

1. **Sample first, format second, route last**
2. **Use Pipe for cross-cutting concerns** — trace ID injection and PII scrubbing belong in middleware
3. **Use `AttrFromContext`** to propagate request-scoped attributes from HTTP middleware to all handlers
4. **Prefer Router over Fanout** when handlers need different record subsets

## Cross-References

- go-error-handling — the log-or-return rule
- go-security — PII handling in logs
- go-samber-oops — structured error context with samber/oops
