---
name: go-samber-mo
description: Monadic types for Go using samber/mo — Option, Result, Either, Future, IO, Task, and State types for type-safe nullable values, error handling, and functional composition with pipeline sub-packages. Apply when using or adopting samber/mo, when the codebase imports github.com/samber/mo, or when considering functional programming patterns as a safety design for Go.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
version: 1.0.0
source: Adapted from samber/cc-skills-golang@golang-samber-mo (MIT License) — https://github.com/samber/cc-skills-golang
---

# samber/mo — Monads and Functional Abstractions for Go

Go 1.18+ library providing type-safe monadic types with zero dependencies. Inspired by Scala, Rust, and fp-ts.

**Official Resources:** [pkg.go.dev/github.com/samber/mo](https://pkg.go.dev/github.com/samber/mo) · [github.com/samber/mo](https://github.com/samber/mo)

```bash
go get github.com/samber/mo
```

## Core Types at a Glance

| Type | Purpose | Think of it as... |
| --- | --- | --- |
| `Option[T]` | Value that may be absent | Rust's `Option`, Java's `Optional` |
| `Result[T]` | Operation that may fail | Rust's `Result<T, E>`, replaces `(T, error)` |
| `Either[L, R]` | Value of one of two types | Scala's `Either`, TypeScript discriminated union |
| `Future[T]` | Async value not yet available | JavaScript `Promise` |
| `IO[T]` | Lazy synchronous side effect | Haskell's `IO` |
| `Task[T]` | Lazy async computation | fp-ts `Task` |
| `State[S, A]` | Stateful computation | Haskell's `State` monad |

## Option[T] — Nullable Values Without nil

```go
import "github.com/samber/mo"

name := mo.Some("Alice")
empty := mo.None[string]()
fromPtr := mo.PointerToOption(ptr) // nil pointer -> None

name.OrElse("Anonymous")  // "Alice"
empty.OrElse("Anonymous") // "Anonymous"

upper := name.Map(func(s string) (string, bool) {
    return strings.ToUpper(s), true
})
```

Key methods: `Some`, `None`, `Get`, `MustGet`, `OrElse`, `OrEmpty`, `Map`, `FlatMap`, `Match`, `ForEach`, `ToPointer`, `IsPresent`, `IsAbsent`. Option implements `json.Marshaler/Unmarshaler`, `sql.Scanner`, `driver.Valuer` — use it directly in JSON structs and database models.

## Result[T] — Error Handling as Values

```go
result := mo.TupleToResult(os.ReadFile("config.yaml"))

upper := mo.Ok("hello").Map(func(s string) (string, error) {
    return strings.ToUpper(s), nil
})
// Ok("HELLO")

val := upper.OrElse("default")
```

**Go limitation:** Direct methods (`.Map`, `.FlatMap`) cannot change the type parameter — `Result[T].Map` returns `Result[T]`, not `Result[U]`. For type-changing transforms, use sub-package functions or `mo.Do`:

```go
import "github.com/samber/mo/result"

parsed := result.Pipe2(
    mo.TupleToResult(os.ReadFile("config.yaml")),
    result.Map(func(data []byte) Config { return parseConfig(data) }),
    result.FlatMap(func(cfg Config) mo.Result[ValidConfig] { return validate(cfg) }),
)
```

Key methods: `Ok`, `Err`, `Errf`, `TupleToResult`, `Try`, `Get`, `MustGet`, `OrElse`, `Map`, `FlatMap`, `MapErr`, `Match`, `ForEach`, `ToEither`, `IsOk`, `IsError`.

## Either[L, R] — Discriminated Union of Two Types

Represents a value that is one of two possible types. Unlike Result, neither side implies success or failure.

```go
func fetchUser(id string) mo.Either[CachedUser, FreshUser] {
    if cached, ok := cache.Get(id); ok {
        return mo.Left[CachedUser, FreshUser](cached)
    }
    return mo.Right[CachedUser, FreshUser](db.Fetch(id))
}
```

**Use Result[T] when one path is an error. Use Either[L, R] when both paths are valid alternatives.** `Either3`/`Either4`/`Either5` extend this to 3-5 type variants.

## Do Notation — Imperative Style with Monadic Safety

`mo.Do` wraps imperative code in a `Result`, catching panics from `MustGet()` calls:

```go
result := mo.Do(func() int {
    a := mo.Some(21).MustGet()
    b := mo.Ok(2).MustGet()
    return a * b // 42
})
// result is Ok(42); a None/Err MustGet() inside Do becomes Err instead of a crash
```

## Pipeline Sub-Packages vs Direct Chaining

**Direct methods** (`.Map`, `.FlatMap`) work when the output type equals the input type. **Sub-package functions** (`option.Map`, `result.Map`) are required when the output type differs. **Pipe functions** (`option.Pipe3`, `result.Pipe3`) chain multiple type-changing transformations readably.

**Rule of thumb:** direct methods for same-type transforms; sub-package functions + pipes when types change across steps.

## Common Patterns

```go
// JSON API responses with Option
type UserResponse struct {
    Name     string            `json:"name"`
    Nickname mo.Option[string] `json:"nickname"` // omits null gracefully
}

// Database nullable columns
type User struct {
    Phone mo.Option[string] // implements sql.Scanner + driver.Valuer
}

// Wrapping existing Go APIs
func MapGet[K comparable, V any](m map[K]V, key K) mo.Option[V] {
    return mo.TupleToOption(m[key])
}

// Uniform extraction with Fold — works across Option, Result, Either
str := mo.Fold[error, int, string](
    mo.Ok(42),
    func(v int) string { return fmt.Sprintf("got %d", v) },
    func(err error) string { return "failed" },
)
```

## Best Practices

1. **Prefer `OrElse` over `MustGet`** — use `MustGet` only inside `mo.Do` blocks or when certain the value exists
2. **Use `TupleToResult` at API boundaries** — convert Go's `(T, error)` to `Result[T]` at the boundary, then chain inside domain logic
3. **Use `Result[T]` for errors, `Either[L, R]` for alternatives**
4. **Option for nullable fields, not zero values** — `Option[string]` distinguishes "absent" from "empty string"
5. **Chain, don't nest** — `result.Map(...).FlatMap(...).OrElse(default)` reads left-to-right
6. **Use sub-package pipes for multi-step type transformations**

If you encounter a bug in samber/mo, open an issue at <https://github.com/samber/mo/issues>.

## Cross-References

- go-samber-lo — functional collection transforms that compose with mo types
- go-error-handling — idiomatic Go error handling patterns
- go-safety — nil-safety and defensive Go coding
- go-database — database access patterns
