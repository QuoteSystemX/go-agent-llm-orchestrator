---
name: go-safety
description: Defensive Go coding to prevent panics, silent data corruption, and subtle runtime bugs. Use when encountering nil panics, append aliasing, map concurrent access, float comparison pitfalls, or zero-value design questions. Also use when reviewing code for nil-safety, numeric conversion overflow, resource lifecycle issues (defer in loops), or defensive copying of slices and maps.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
version: 1.0.0
source: Adapted from samber/cc-skills-golang@golang-safety (MIT License) — https://github.com/samber/cc-skills-golang
---

# Go Safety: Correctness & Defensive Coding

Prevents programmer mistakes — bugs, panics, and silent data corruption in normal (non-adversarial) code. Security handles attackers (see go-security); safety handles ourselves.

## Best Practices Summary

1. **Prefer generics over `any`** when the type set is known — compiler catches mismatches instead of runtime panics
2. **Always use safe type assertions** — comma-ok (`v, ok := x.(T)`) for interfaces; Go 1.25+ prefer `reflect.TypeAssert[T]` over `value.Interface().(T)` for reflection code
3. **Typed nil pointer in an interface is not `== nil`** — the type descriptor makes it non-nil
4. **Writing to a nil map panics** — always initialize before use
5. **`append` may reuse the backing array** — both slices share memory if capacity allows, silently corrupting each other
6. **Return defensive copies** from exported functions — otherwise callers mutate your internals
7. **`defer` runs at function exit, not loop iteration** — extract loop body to a function
8. **Integer conversions truncate silently** — `int64` to `int32` wraps without error
9. **Float arithmetic is not exact** — use epsilon comparison or `math/big`
10. **Design useful zero values** — nil map fields panic on first write; use lazy init
11. **Use `sync.Once` for lazy init** — guarantees exactly-once even under concurrency

## Nil Safety

### The nil interface trap

Interfaces store (type, value). An interface is `nil` only when both are nil. Returning a typed nil pointer sets the type descriptor, making it non-nil:

```go
// ✗ Dangerous — interface{type: *MyHandler, value: nil} is not == nil
func getHandler() http.Handler {
    var h *MyHandler
    if !enabled { return h }
    return h
}

// ✓ Good — return nil explicitly
func getHandler() http.Handler {
    if !enabled { return nil }
    return &MyHandler{}
}
```

### Nil map, slice, and channel behavior

| Type | Index into nil | Write to nil | Len/Cap of nil | Range over nil |
| --- | --- | --- | --- | --- |
| Map | Zero value | **panic** | 0 | 0 iterations |
| Slice | **panic** | **panic** | 0 | 0 iterations |
| Channel | Blocks forever | Blocks forever | 0 | Blocks forever |

```go
// ✗ Bad — nil map panics on write
var m map[string]int
m["key"] = 1

// ✓ Good — lazy-init in methods
func (r *Registry) Add(name string, val int) {
    if r.items == nil { r.items = make(map[string]int) }
    r.items[name] = val
}
```

## Slice & Map Safety

### Slice aliasing — the append trap

`append` reuses the backing array if capacity allows. Both slices then share memory:

```go
// ✗ Dangerous — a and b share backing array
a := make([]int, 3, 5)
b := append(a, 4)
b[0] = 99 // also modifies a[0]

// ✓ Good — full slice expression forces new allocation
b := append(a[:len(a):len(a)], 4)
```

### Map concurrent access

Maps MUST NOT be accessed concurrently — see go-concurrency for sync primitives.

## Numeric Safety

### Implicit type conversions truncate silently

```go
// ✗ Bad — silently wraps around if val > math.MaxInt32
var val int64 = 3_000_000_000
i32 := int32(val) // -1294967296 (silent wraparound)

// ✓ Good — check before converting
if val > math.MaxInt32 || val < math.MinInt32 {
    return fmt.Errorf("value %d overflows int32", val)
}
i32 := int32(val)
```

### Float comparison

```go
// ✗ Bad
var a, b, c float64 = 0.1, 0.2, 0.3
a+b == c // false

// ✓ Good
const epsilon = 1e-9
math.Abs((a+b)-c) < epsilon // true
```

### Division by zero

Integer division by zero panics. Float division by zero produces `+Inf`, `-Inf`, or `NaN`.

```go
func avg(total, count int) (int, error) {
    if count == 0 {
        return 0, errors.New("division by zero")
    }
    return total / count, nil
}
```

For integer overflow as a security vulnerability, see go-security.

## Resource Safety

### defer in loops — resource accumulation

`defer` runs at _function_ exit, not loop iteration. Resources accumulate until the function returns:

```go
// ✗ Bad — all files stay open until function returns
for _, path := range paths {
    f, _ := os.Open(path)
    defer f.Close()
    process(f)
}

// ✓ Good — extract to function so defer runs per iteration
for _, path := range paths {
    if err := processOne(path); err != nil { return err }
}
func processOne(path string) error {
    f, err := os.Open(path)
    if err != nil { return err }
    defer f.Close()
    return process(f)
}
```

### Goroutine leaks

See go-concurrency for goroutine lifecycle and leak prevention.

## Immutability & Defensive Copying

Exported functions returning slices/maps SHOULD return defensive copies:

```go
// ✗ Bad — exported slice field, anyone can mutate
type Config struct { Hosts []string }

// ✓ Good — unexported field with accessor returning a copy
type Config struct { hosts []string }
func (c *Config) Hosts() []string { return slices.Clone(c.hosts) }
```

## Initialization Safety

### Zero-value design

```go
var mu sync.Mutex    // ✓ usable at zero value
var buf bytes.Buffer // ✓ usable at zero value

// ✗ Bad — nil map panics on write
type Cache struct { data map[string]any }
```

### sync.Once for lazy initialization

```go
type DB struct {
    once sync.Once
    conn *sql.DB
}
func (db *DB) connection() *sql.DB {
    db.once.Do(func() {
        db.conn, _ = sql.Open("postgres", connStr)
    })
    return db.conn
}
```

## Enforce with Linters

Many safety pitfalls are caught automatically: `errcheck`, `forcetypeassert`, `nilerr`, `govet`, `staticcheck`.

## Common Mistakes

| Mistake | Fix |
| --- | --- |
| Bare type assertion `v := x.(T)` | Panics on mismatch. Use `v, ok := x.(T)` |
| Returning typed nil in interface function | Interface holds (type, nil) which is != nil. Return untyped `nil` |
| Writing to a nil map | Nil maps have no backing storage — write panics. Use `make(map[K]V)` |
| Assuming `append` always copies | If capacity allows, both slices share the backing array. Use `s[:len(s):len(s)]` |
| `defer` in a loop | Runs at function exit, not loop iteration — extract body to a function |
| `int64` to `int32` without bounds check | Values wrap silently. Check against `math.MaxInt32`/`math.MinInt32` first |
| Comparing floats with `==` | IEEE 754 is not exact. Use `math.Abs(a-b) < epsilon` |
| Integer division without zero check | Panics. Guard with `if divisor == 0` |
| Returning internal slice/map reference | Callers can mutate your struct's internals. Return a defensive copy |
| Blocking forever on nil channel | Nil channels block on both send and receive. Always initialize before use |

## Cross-References

- go-concurrency — concurrent access patterns and sync primitives
- go-data-structures — slice/map internals, capacity growth, and container/ packages
- go-error-handling — nil error interface trap
- go-security — security-relevant safety issues (memory safety, integer overflow)
- go-troubleshooting — debugging panics and race conditions
