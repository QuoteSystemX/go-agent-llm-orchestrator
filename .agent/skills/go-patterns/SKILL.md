---
name: go-patterns
description: Professional Go development principles for 2025. Covers Gin/Echo/Fiber, gRPC with buf, logrus, vault, and high-performance concurrency.
allowed-tools: Read, Write, Edit, Glob, Grep
---

# Go Patterns

> Expert Go development principles for high-performance, concurrent systems.
> **Pass the context, handle the errors, and keep it fast.**

---

## ⚠️ Core Directive: Context Management

In this workspace, context is sacred.

- **RULE 1**: Always pass `ctx context.Context` as the first parameter to functions that perform I/O or long-running tasks.
- **RULE 2**: NEVER use `context.Background()` or `context.TODO()` in production code.
- **RULE 3**: `context.Background()` is ONLY permitted in **test files** (`*_test.go`) or the absolute entry point of the application (`main.go`).
- **RULE 4**: If a function needs a context but wasn't passed one, refactor the caller to provide it.

---

## 1. Logging with Logrus

Logrus is the standard structured logger for this environment.

```go
// Preferred pattern
log.WithFields(logrus.Fields{
    "component": "price-engine",
    "request_id": reqID,
}).Info("processing price update")
```

### Best Practices

- Always use structured fields instead of `fmt.Sprintf` in messages.
- Use `logrus.WithContext(ctx)` if tracing integration is available.
- Define common fields at the logger creation level (e.g., app name, environment).

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

## 3. High Performance Concurrency (`xsync`)

When performance is critical and maps are highly contended, use `puzpuzpuz/xsync`.

- **xsync.Map**: 96.5% better read performance than `sync.RWMutex` and significantly faster than `sync.Map` for write-heavy or mixed workloads.
- **Why**: Lock-free or fine-grained locking mechanisms optimized for modern CPUs.

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

## 7. Framework Selection (2025)

| Framework | Best For |
|-----------|----------|
| **Standard library** | Core services, minimal overhead. |
| **Gin** | Middlewares, JSON APIs, high speed. |
| **Echo** | Clean API design, high performance. |
| **Fiber** | Extreme performance (fasthttp based). |

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
| **Used Logrus?**                  | Structured logging only.                |
| **Used Decimal?**                 | Mandatory for financial math.           |
| **Used Squirrel?**                | Safe SQL building.                      |
| **Used xsync?**                   | High-contention map performance.        |

---

> **Remember**: Go is about simplicity and clarity. Write code that is easy to read, easy to test, and safe to run in parallel.
