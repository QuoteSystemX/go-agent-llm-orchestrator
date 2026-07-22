---
name: go-context
description: Idiomatic context.Context usage in Go — propagation through API boundaries, cancellation, timeouts and deadlines, request-scoped values, context.WithoutCancel for background work outliving requests. Apply when designing context propagation across layers, debugging leaked or unexpired contexts, choosing between context.Background/TODO/WithoutCancel, or storing values in context. Not for code that merely accepts ctx as first parameter.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
version: 1.0.0
source: Adapted from samber/cc-skills-golang@golang-context (MIT License) — https://github.com/samber/cc-skills-golang
---

# Go context.Context Best Practices

`context.Context` is Go's mechanism for propagating cancellation signals, deadlines, and request-scoped values across API boundaries and between goroutines — the "session" of a request.

## Best Practices Summary

1. The same context MUST be propagated through the entire request lifecycle: HTTP handler → service → DB → external APIs
2. `ctx` MUST be the first parameter, named `ctx context.Context`
3. NEVER store context in a struct — pass explicitly through function parameters
4. NEVER pass `nil` context — use `context.TODO()` if unsure
5. `cancel()` MUST be called on all control-flow paths for `WithCancel`/`WithTimeout`/`WithDeadline`, unless ownership is explicitly transferred
6. `context.Background()` MUST only be used at the top level (main, init, tests)
7. **Use `context.TODO()`** as a placeholder when you know a context is needed but don't have one yet
8. NEVER create a new `context.Background()` in the middle of a request path
9. Context value keys MUST be unexported types to prevent collisions
10. Context values MUST only carry request-scoped metadata — NEVER function parameters
11. **Use `context.WithoutCancel`** (Go 1.21+) when spawning background work that must outlive the parent request

## Creating Contexts

| Situation | Use |
| --- | --- |
| Entry point (main, init, test) | `context.Background()` |
| Function needs context but caller doesn't provide one yet | `context.TODO()` |
| Inside an HTTP handler | `r.Context()` |
| Need cancellation control | `context.WithCancel(parentCtx)` |
| Need a deadline/timeout | `context.WithTimeout(parentCtx, duration)` |

## Context Propagation: The Core Principle

**Propagate the same context through the entire call chain.** When you propagate correctly, cancelling the parent context cancels all downstream work automatically.

```go
// ✗ Bad — creates a new context, breaking the chain
func (s *OrderService) Create(ctx context.Context, order Order) error {
    return s.db.ExecContext(context.Background(), "INSERT INTO orders ...", order.ID)
}

// ✓ Good — propagates the caller's context
func (s *OrderService) Create(ctx context.Context, order Order) error {
    return s.db.ExecContext(ctx, "INSERT INTO orders ...", order.ID)
}
```

## Cancellation, Timeouts & Deadlines

`WithCancel` for manual cancellation, `WithTimeout` for automatic cancellation after a duration, `WithDeadline` for absolute time deadlines. Listen with `<-ctx.Done()` in concurrent code. Use `context.WithoutCancel` for operations that must outlive their parent request (e.g. audit logs written after the HTTP response is sent).

## Context Values & Cross-Service Tracing

Use unexported key types to prevent namespace collisions:

```go
type contextKey string
const requestIDKey contextKey = "requestID"

ctx = context.WithValue(ctx, requestIDKey, reqID)
```

Use context values only for request-scoped metadata (request ID, user ID, trace ID) — never for passing function parameters, which belong in the function signature. For cross-service tracing, propagate OpenTelemetry trace headers and correlation IDs through context for log aggregation.

## Context in HTTP Servers & Service Calls

- **HTTP handler**: `r.Context()` for request-scoped cancellation, propagate to services
- **HTTP client**: `NewRequestWithContext`, client timeouts, retries with context awareness
- **Database operations**: always use `*Context` variants (`QueryContext`, `ExecContext`) to respect deadlines

## Cross-References

- go-concurrency — goroutine cancellation patterns using context
- go-database — context-aware database operations (QueryContext, ExecContext)
- go-design-patterns — timeout and resilience patterns

## Enforce with Linters

Many context pitfalls are caught automatically: `govet`, `staticcheck`.
