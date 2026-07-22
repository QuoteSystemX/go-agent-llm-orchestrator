---
name: go-samber-do
description: Dependency injection in Go using samber/do — service containers, lifecycle management, scopes, health checks, graceful shutdown, and module organization. Apply when using or adopting samber/do, when the codebase imports github.com/samber/do/v2, or when refactoring manual constructor injection into a DI container.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
version: 1.0.0
source: Adapted from samber/cc-skills-golang@golang-samber-do (MIT License) — https://github.com/samber/cc-skills-golang
---

# Using samber/do for Dependency Injection in Go

Type-safe dependency injection toolkit for Go based on Go 1.18+ generics.

**Official Resources:** [pkg.go.dev/github.com/samber/do/v2](https://pkg.go.dev/github.com/samber/do/v2) · [do.samber.dev](https://do.samber.dev) · [github.com/samber/do/v2](https://github.com/samber/do)

DO NOT USE v1 OF THIS LIBRARY. INSTALL v2 INSTEAD:

```bash
go get -u github.com/samber/do/v2
```

## Core Concepts

### The Injector (Container)

```go
import "github.com/samber/do/v2"
injector := do.New()
```

### Service Types

- **Lazy** (default): created when first requested
- **Eager**: created immediately when the container starts
- **Transient**: new instance created on every request
- **Value**: pre-created value, no instantiation

## Basic Usage

### 1. Define and Register Services

Follow "Accept Interfaces, Return Structs":

```go
// Register a service (lazy by default)
do.Provide(injector, func(i do.Injector) (Database, error) {
    return &PostgreSQLDatabase{connString: "postgres://..."}, nil
})

// Register a pre-created value
do.ProvideValue(injector, &Config{Port: 8080})

// Register a transient service (new instance each time)
do.ProvideTransient(injector, func(i do.Injector) (*Logger, error) {
    return &Logger{}, nil
})
```

### 2. Invoke Services

```go
db, err := do.Invoke[Database](injector)     // with error handling
db := do.MustInvoke[Database](injector)      // panics on error
```

### 3. Service Dependencies

```go
func NewUserService(i do.Injector) (UserService, error) {
    db := do.MustInvoke[Database](i)
    cache := do.MustInvoke[Cache](i)
    return &userService{db: db, cache: cache}, nil
}
do.Provide(injector, NewUserService)
```

### 4. Implicit Aliasing (Preferred)

```go
do.Provide(injector, func(i do.Injector) (*PostgreSQLDatabase, error) {
    return &PostgreSQLDatabase{}, nil
})
db := do.MustInvokeAs[Database](injector) // invoke concrete type as interface
```

### 5. Named Services

```go
do.ProvideNamed(injector, "primary-db", func(i do.Injector) (*Database, error) {
    return &Database{URL: "postgres://primary..."}, nil
})
mainDB := do.MustInvokeNamed[*Database](injector, "primary-db")
```

## Package Organization

```go
// infrastructure/package.go
var Package = do.Package(
    do.Lazy(func(i do.Injector) (*postgres.DB, error) {
        cfg := do.MustInvoke[*Config](i)
        return postgres.Connect(cfg.DatabaseURL)
    }),
)

// main.go
injector := do.New(infrastructure.Package, service.Package)
```

## Full Application Setup

```go
func main() {
    injector := do.New(
        infrastructure.Package,
        repository.Package,
        service.Package,
        transport.Package,
    )
    server := do.MustInvoke[*http.Server](injector)
    go server.ListenAndServe()
    _ = injector.ShutdownOnSignalsWithContext(context.Background(), os.Interrupt)
}
```

## Best Practices

1. Depend on interfaces, not concrete types — lets you swap implementations in tests
2. Each service should have one job — services with multiple responsibilities are harder to test and replace
3. Keep dependency trees shallow — chains beyond 3-4 levels make initialization order fragile
4. Handle errors in provider functions — a silently failing provider creates a broken service that crashes later unexpectedly
5. Use scopes to organize services by lifecycle — request-scoped services prevent leaks, global services prevent redundant initialization

## Quick Reference

### Registration

| Function | Purpose |
| --- | --- |
| `do.Provide[T]()` | Register lazy service (default) |
| `do.ProvideNamed[T]()` | Register named lazy service |
| `do.ProvideValue[T]()` | Register pre-created value |
| `do.ProvideTransient[T]()` | Register new instance each time |
| `do.Package()` | Group service registrations |

### Invocation

| Function | Purpose |
| --- | --- |
| `do.Invoke[T]()` | Get service (with error) |
| `do.InvokeNamed[T]()` | Get named service |
| `do.InvokeAs[T]()` | Get first service matching interface |
| `do.InvokeStruct[T]()` | Inject into struct fields using tags |
| `do.MustInvoke[T]()` | Get service (panic on error) |
| `do.MustInvokeAs[T]()` | Get service by interface (panic on error) |
| `do.MustInvokeStruct[T]()` | Inject into struct (panic on error) |

## Cross-References

- go-design-patterns — comparison with functional options and when a DI library is worth adopting
- go-data-structures — interface design patterns
- go-testing — general testing patterns
