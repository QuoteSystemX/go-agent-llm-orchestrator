---
name: go-error-handling
description: Idiomatic Go error handling — creation, wrapping with %w, errors.Is/As, errors.Join, custom error types, sentinel errors, panic/recover, the single handling rule, and structured logging with slog. Apply when creating, wrapping, inspecting, or logging errors in Go code. For samber/oops specifics see go-samber-oops; for the slog handler ecosystem see go-samber-slog.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
version: 1.0.0
source: Adapted from samber/cc-skills-golang@golang-error-handling (MIT License) — https://github.com/samber/cc-skills-golang
---

# Go Error Handling Best Practices

Robust, idiomatic error handling in Go applications — maintainable, debuggable, and production-ready.

## Best Practices Summary

1. **Returned errors MUST always be checked** — NEVER discard with `_`
2. **Errors MUST be wrapped with context** using `fmt.Errorf("{context}: %w", err)`
3. **Error strings MUST be lowercase**, without trailing punctuation
4. **Use `%w` internally, `%v` at system boundaries** to control error chain exposure
5. **MUST use `errors.Is` for sentinel matching and `errors.As`/`errors.AsType` for typed chain inspection** instead of direct comparison or bare type assertions. For Go 1.26+, prefer `errors.AsType[T](err)` when `T` implements `error`; use `errors.As(err, &target)` for Go <1.26 or non-error interface targets
6. **SHOULD use `errors.Join`** (Go 1.20+) to combine independent errors
7. **Errors MUST be either logged OR returned**, NEVER both (single handling rule)
8. **Use sentinel errors** for expected conditions, custom types for carrying data
9. **NEVER use `panic` for expected error conditions** — reserve for truly unrecoverable states
10. **SHOULD use `slog`** (Go 1.21+) for structured error logging — not `fmt.Println` or `log.Printf`
11. **Use `samber/oops`** (see go-samber-oops) for production errors needing stack traces, user/tenant context, or structured attributes
12. **Log HTTP requests** with structured middleware capturing method, path, status, and duration
13. **Use log levels** to indicate error severity
14. **Never expose technical errors to users** — translate internal errors to user-friendly messages, log technical details separately
15. **Keep log grouping low-cardinality** — attach IDs, paths, and counts as structured attributes rather than interpolating them into the stable log message used for grouping

## Error Creation

Error messages should be lowercase, no punctuation, and describe what happened without prescribing action:

```go
// ✓ Good
return errors.New("connection refused")
return fmt.Errorf("parsing config: %w", err)

// ✗ Bad
return errors.New("Connection Refused.")
```

### Sentinel errors — preallocated, compared with errors.Is

```go
var ErrNotFound = errors.New("mypackage: not found")

if errors.Is(err, ErrNotFound) { ... }
```

### Custom error types — for carrying rich context

```go
type ValidationError struct {
    Field string
    Value any
}

func (e *ValidationError) Error() string {
    return fmt.Sprintf("invalid value for field %q", e.Field)
}
```

## Error Wrapping and Inspection

`fmt.Errorf("{context}: %w", err)` preserves the chain — `%v` breaks it into flat text. Use `errors.Is` for sentinel matching, `errors.As` (or Go 1.26+ `errors.AsType[T]`) for typed inspection, and `errors.Join` to combine independent errors:

```go
if err != nil {
    return fmt.Errorf("fetching user %s: %w", id, err)
}

var pathErr *fs.PathError
if errors.As(err, &pathErr) {
    // handle pathErr.Path, pathErr.Op
}

combined := errors.Join(err1, err2)
```

## The Single Handling Rule

Errors are either logged OR returned, NEVER both — logging at every layer as an error propagates up produces duplicate, cluttered log entries in aggregators.

```go
// ✗ Bad — logged here AND returned, will be logged again upstream
func fetch() error {
    if err != nil {
        log.Error("fetch failed", "err", err)
        return err
    }
}

// ✓ Good — wrap with context and return; log once at the top
func fetch() error {
    if err != nil {
        return fmt.Errorf("fetching: %w", err)
    }
}
```

## Panic and Recover

`panic` is for truly unrecoverable states (violated invariants, `Must*` constructors at init time) — never for expected error conditions a caller could handle. Recover at goroutine boundaries to prevent one goroutine's panic from crashing the process.

## Structured Logging

Use `slog` (Go 1.21+) for structured error logging:

```go
slog.ErrorContext(ctx, "failed to process order",
    slog.String("order_id", orderID),
    slog.Any("error", err),
)
```

For production errors needing stack traces, user/tenant context, and structured attributes, use `samber/oops` (go-samber-oops). For multi-handler routing, sampling, and backend sinks, see go-samber-slog.

## Cross-References

- go-samber-oops — full samber/oops API, builder patterns, and logger integration
- go-samber-slog — structured logging setup, log levels, and request logging middleware
- go-safety — nil interface trap and nil error comparison pitfalls
- go-naming — error naming conventions (ErrNotFound, PathError)

## References

- [samber/oops](https://github.com/samber/oops)
- [samber/slog-multi](https://github.com/samber/slog-multi)
- [log/slog package](https://pkg.go.dev/log/slog)
