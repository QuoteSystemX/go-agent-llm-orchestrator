---
name: go-patterns
description: Professional Go development principles for 2026. Covers slog, gRPC with buf, high-performance lock-free concurrency, and zero-allocation patterns.
allowed-tools: Read, Write, Edit, Glob, Grep
version: 1.0.0
---

# Go Patterns

> Expert Go development principles for high-performance, concurrent systems.
> **Pass the context, use slog, handle errors, and aim for zero-alloc.**

---

## ⚠️ Core Directive: Context Management

In this workspace, context is sacred.

- **RULE 1**: Always pass `ctx context.Context` as the first parameter to functions that perform I/O or long-running tasks.
- **RULE 2**: NEVER use `context.Background()` or `context.TODO()` in production code.
- **RULE 3**: `context.Background()` is ONLY permitted in **test files** (`*_test.go`) or the absolute entry point of the application (`main.go`).
- **RULE 4**: If a function needs a context but wasn't passed one, refactor the caller to provide it.

---

## 1. Logging with `log/slog` (Standard)

The standard library `slog` is the mandatory logger for 2026.

```go
// Preferred pattern
slog.InfoContext(ctx, "processing price update",
    slog.String("component", "price-engine"),
    slog.String("request_id", reqID),
)
```

### Best Practices

- Use `InfoContext`, `ErrorContext` etc., to propagate trace IDs from context.
- Always use strongly typed attributes (`slog.String`, `slog.Int`) to avoid reflection.
- Define a global logger with `slog.SetDefault` in `main.go`.

---

## 2. SQL Building with Squirrel

Avoid raw string concatenation. Use **Squirrel** for dynamic and clean SQL building.

```go
users := squirrel.Select("*").From("users").Where(squirrel.Eq{"active": true})
sql, args, err := users.ToSql()
```

### Best Practices:
- Combine with `pgx` for high-performance PostgreSQL interaction.
- Use `squirrel.PlaceholderFormat(squirrel.Dollar)` for Postgres.

---

## 3. High Performance Concurrency (`xsync` & Lock-Free)

When performance is critical and maps are highly contended, use specialized lock-free libraries.

| Library | Purpose | Benefit |
|---------|---------|---------|
| `puzpuzpuz/xsync/v4` | `MapOf`, `Counter` | Lock-free reads, localized locking for writes. |
| `alphadose/zenq` | Thread-safe queue | Multi-producer, multi-consumer lock-free queue. |
| `panjf2000/ants/v2` | Goroutine pool | Limits concurrency, reuses goroutines, reduces GC. |
| `uber-go/atomic` | Typed atomics | Wrapper for `sync/atomic` with better type safety. |

### ⚡ Lock-Free Patterns: CAS (Compare-And-Swap)
```go
import "sync/atomic"

var value atomic.Int64
// ...
if value.CompareAndSwap(old, new) {
    // success
}
```

### ⚡ False Sharing Prevention
Add padding to structs to avoid cache line contention.
```go
type HotData struct {
    Val1 int64
    _    [56]byte // Padding to 64 bytes (cache line size)
    Val2 int64
}
```

---

## 4. Financial Accuracy (`decimal`)

**NEVER** use `float64` for money, prices, or exact quote values.

- Use `github.com/shopspring/decimal`.
- Perform all calculations (Add, Sub, Mul, Div) using library methods.
- Only convert to float/string for final display or legacy API compatibility.

---

## 5. Secrets Management (Vault & Infisical)

- **HashiCorp Vault**: Primary for production secrets and dynamic credentials.
- **Infisical**: Alternative for developer secrets and centralized config.
- **Rule**: Never commit secrets to Git. Use `cleanenv` to bind environment variables into Go structs.

---

## 6. Protobuf & gRPC with `buf`

Modern gRPC development uses [buf.build](https://buf.build) for better linting and generation management.

### Best Practices:
- Always define package versions (e.g., `package api.v1;`).
- Use `buf lint` to ensure API consistency.
- Use `buf generate` to create Go code.

---

## 7. Framework Selection (2026)

| Framework | Best For | Note |
|-----------|----------|------|
| **Standard library** | Core services, minimal overhead. | Recommended for 2026. |
| **Gin** | Middlewares, JSON APIs. | Fast, but uses reflection. |
| **Fiber** | Extreme performance. | Based on `fasthttp`. |

### ⚡ Zero-Allocation Design
- **`fasthttp`**: Use instead of `net/http` for high-throughput edge services.
- **`sync.Pool`**: Reuse objects (buffers, structs) on the hot path to eliminate GC pauses.
- **`tidwall/gjson`**: Extract JSON fields without full parsing or allocation.

---

## 8. Error Handling

- Use `%w` for error wrapping: `fmt.Errorf("doing thing: %w", err)`.
- Use `errors.Is` and `errors.As` for checking.
- **Explicit over Implicit**: Check every error immediately.

---

## 10. Decision Checklist

| **Check**                         | **Focus**                               |
|-----------------------------------|-----------------------------------------|
| **Passed context properly?**      | No `Background()` in production!        |
| **Used slog?**                    | Standard library structured logging.    |
| **Used Decimal?**                 | Mandatory for financial math.           |
| **Used xsync/Lock-free?**         | High-contention performance.            |
| **Used sync.Pool?**               | Zero-allocation on hot paths.           |
| **Applied PGO?**                 | Profile-Guided Optimization (+10% perf).|

---

## 🚀 Deep Performance: Tier 3 (Expert)

### 1. PGO (Profile-Guided Optimization)
Go 1.21+ can use production profiles to optimize the next build.
- **Workflow**:
  1. Build a default binary.
  2. Collect profile: `curl http://localhost:6060/debug/pprof/profile?seconds=30 -o default.pgo`.
  3. Rebuild with profile: `go build -pgo=default.pgo`.
- **Result**: Better inlining and code layout based on hot paths.

### 2. SIMD & Assembly
When standard Go code isn't fast enough for data processing (hashing, crypto, image processing).
- **Tool**: `github.com/klauspost/cpuid` to detect CPU features.
- **Approach**: Use Plan9 Assembly or `github.com/segmentio/asm` for vector instructions.

### 3. Escape Analysis Tuning
Force variables to stay on the **Stack** to avoid GC pressure.
- **Check**: `go build -gcflags="-m -l" .` (m=move, l=inline).
- **Rule**: Avoid passing pointers to small structs; use values instead. A pointer to an `int` often escapes to the heap, costing more than the copy.

### 4. Memory Layout & Alignment
The order of fields in a struct matters.
```go
// ❌ Bad: 24 bytes (due to padding)
type Bad struct {
    A bool  // 1 byte
    B int64 // 8 bytes (needs 8-byte alignment, 7 bytes padding added)
    C bool  // 1 byte (7 bytes padding added at end)
}

// ✅ Good: 16 bytes
type Good struct {
    B int64 // 8 bytes
    A bool  // 1 byte
    C bool  // 1 byte
    _ [6]byte // Manual padding to 8-byte alignment
}
```
- **Tool**: `fieldalignment` from `golang.org/x/tools/go/analysis/passes/fieldalignment`.

---

> **Remember**: Go is about simplicity and clarity. Write code that is easy to read, easy to test, and safe to run in parallel.

## Changelog

- **1.2.0** (2026-05-08): Added Tier 3 Expert patterns: PGO, SIMD, Escape Analysis, Alignment.
- **1.1.0** (2026-05-08): Upgraded to 2026 standards: slog, lock-free, zero-alloc.
- **1.0.0** (2026-04-26): Initial version
