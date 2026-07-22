---
name: go-samber-oops
description: Structured error handling in Go with samber/oops — error builders, stack traces, error codes, error context, error wrapping, error attributes, user-facing vs developer messages, panic recovery, and logger integration. Apply when using or adopting samber/oops, or when the codebase already imports github.com/samber/oops.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
version: 1.0.0
source: Adapted from samber/cc-skills-golang@golang-samber-oops (MIT License) — https://github.com/samber/cc-skills-golang
---

# samber/oops Structured Error Handling

A drop-in replacement for Go's standard error handling that adds structured context, stack traces, error codes, public messages, and panic recovery. Variable data goes in `.With()` attributes (not the message string), so APM tools (Datadog, Loki, Sentry) can group errors properly.

## Why use samber/oops

Standard Go errors lack context — `connection failed` doesn't say which user triggered it or what the call stack was. `samber/oops` provides structured context, automatic stack traces, machine-readable error codes, user-safe public messages, and low-cardinality messages for APM grouping.

## Core pattern: Error builder chain

```go
err := oops.
    In("user-service").
    Tags("database", "postgres").
    Code("network_failure").
    User("user-123", "email", "foo@bar.com").
    With("query", query).
    Errorf("failed to fetch user: %s", "timeout")
```

Terminal methods: `.Errorf(format, args...)`, `.Wrap(err)`, `.Wrapf(err, format, args...)`, `.Join(err1, err2, ...)`, `.Recover(fn)` / `.Recoverf(fn, format, args...)`.

### Error builder methods

| Method | Use case |
| --- | --- |
| `.With("key", value)` | Add custom key-value attribute |
| `.WithContext(ctx, "key1", "key2")` | Extract values from Go context into attributes |
| `.In("domain")` | Set the feature/service/domain |
| `.Tags("auth", "sql")` | Add categorization tags |
| `.Code("iam_authz_missing_permission")` | Machine-readable error identifier |
| `.Public("Could not fetch user.")` | User-safe message (separate from technical details) |
| `.Hint("Runbook: https://doc.acme.org/doc/abcd.md")` | Debugging hint |
| `.Owner("team/slack")` | Responsible team/owner |
| `.User(id, "k", "v")` | User identifier and attributes |
| `.Tenant(id, "k", "v")` | Tenant/organization context |
| `.Trace(id)` / `.Span(id)` | Correlation ID / unit of work |
| `.Request(req, includeBody)` / `.Response(res, includeBody)` | Attach HTTP req/res |
| `oops.FromContext(ctx)` | Start from a builder stored in a Go context |

## Common scenarios

### Database/repository layer

```go
func (r *UserRepository) FetchUser(id string) (*User, error) {
    query := "SELECT * FROM users WHERE id = $1"
    row, err := r.db.Query(query, id)
    if err != nil {
        return nil, oops.
            In("user-repository").
            Tags("database", "postgres").
            With("query", query).
            With("user_id", id).
            Wrapf(err, "failed to fetch user from database")
    }
}
```

### HTTP handler layer

```go
func (h *Handler) CreateUser(w http.ResponseWriter, r *http.Request) {
    err := h.service.CreateUser(r.Context(), getUserID(r))
    if err != nil {
        err = oops.In("http-handler").Request(r, false).Wrapf(err, "create user failed")
        http.Error(w, oops.GetPublic(err, "Internal server error"), http.StatusInternalServerError)
        return
    }
}
```

## Error wrapping best practices

```go
// ✓ Good — Wrap returns nil if err is nil, no nil check needed
return oops.Wrapf(err, "operation failed")

// ✗ Bad — unnecessary nil check
if err != nil { return oops.Wrapf(err, "operation failed") }
return nil
```

Each architectural layer SHOULD add context via Wrap/Wrapf — at least once per package boundary:

```go
func Controller() error {
    return oops.In("controller").Trace(traceID).Wrapf(Service(), "user request failed")
}
func Service() error {
    return oops.In("service").With("op", "create_user").Wrapf(Repository(), "db operation failed")
}
```

### Keep error messages low-cardinality

```go
// ✗ Bad — high-cardinality, breaks APM grouping
oops.Errorf("failed to process user %s in tenant %s", userID, tenantID)

// ✓ Good — static message + structured attributes
oops.With("user_id", userID).With("tenant_id", tenantID).Errorf("failed to process user")
```

## Panic recovery

`oops.Recover()` MUST be used in goroutine boundaries:

```go
func ProcessData(data string) (err error) {
    return oops.
        In("data-processor").
        Code("panic_recovered").
        With("input_data", data).
        Recover(func() { riskyOperation(data) })
}
```

## Accessing error information

```go
if oopsErr, ok := err.(oops.OopsError); ok {
    fmt.Println("Code:", oopsErr.Code())
    fmt.Println("Domain:", oopsErr.Domain())
    fmt.Println("Stacktrace:", oopsErr.Stacktrace())
}
publicMsg := oops.GetPublic(err, "Something went wrong")
```

```go
fmt.Printf("%+v\n", err)       // verbose with stack trace
bytes, _ := json.Marshal(err)  // JSON for logging
slog.Error(err.Error(), slog.Any("error", err))
```

## Context propagation

```go
func middleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        builder := oops.In("http").Request(r, false).Trace(r.Header.Get("X-Trace-ID"))
        ctx := oops.WithBuilder(r.Context(), builder)
        next.ServeHTTP(w, r.WithContext(ctx))
    })
}
func handler(ctx context.Context) error {
    return oops.FromContext(ctx).Tags("handler", "users").Errorf("something failed")
}
```

If you encounter a bug in samber/oops, open an issue at <https://github.com/samber/oops/issues>.

## References

- [github.com/samber/oops](https://github.com/samber/oops)

## Cross-References

- go-error-handling — general error handling patterns
- go-samber-slog — logger integration and structured logging
