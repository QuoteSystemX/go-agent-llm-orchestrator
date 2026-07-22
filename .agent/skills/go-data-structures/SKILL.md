---
name: go-data-structures
description: Go data structures — slices (internals, capacity growth, preallocation, slices package), maps (internals, hash buckets, maps package), arrays, container/list/heap/ring, strings.Builder vs bytes.Buffer, generic collections, pointers (unsafe.Pointer, weak.Pointer), and copy semantics. Use when choosing or optimizing Go data structures, implementing generic containers, or questioning slice/map internals.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
version: 1.0.0
source: Adapted from samber/cc-skills-golang@golang-data-structures (MIT License) — https://github.com/samber/cc-skills-golang
---

# Go Data Structures

Built-in and standard library data structures: internals, correct usage, and selection guidance. For safety pitfalls (nil maps, append aliasing, defensive copies) see go-safety. For channels and sync primitives see go-concurrency.

## Best Practices Summary

1. **Preallocate slices and maps** with `make(T, 0, n)` / `make(map[K]V, n)` when size is known or estimable
2. **Arrays** SHOULD be preferred over slices only for fixed, compile-time-known sizes (hash digests, IPv4 addresses)
3. **NEVER rely on slice capacity growth timing** — the growth algorithm changed between Go versions and may change again
4. **Use `container/heap`** for priority queues, **`container/list`** only when frequent middle insertions are needed, **`container/ring`** for fixed-size circular buffers
5. **`strings.Builder`** MUST be preferred for building strings; **`bytes.Buffer`** MUST be preferred for bidirectional I/O
6. Generic data structures SHOULD use the **tightest constraint** possible — `comparable` for keys, custom interfaces for ordering
7. **`unsafe.Pointer`** MUST only follow the 6 valid conversion patterns from the Go spec — NEVER store in a `uintptr` variable across statements
8. **`weak.Pointer[T]`** (Go 1.24+) SHOULD be used for caches and canonicalization maps to allow GC to reclaim entries

## Slice Internals

A slice is a 3-word header: pointer, length, capacity. Multiple slices can share a backing array (see go-safety for aliasing traps).

### Capacity Growth

- < 256 elements: capacity doubles
- ≥ 256 elements: grows by ~25% (`newcap += (newcap + 3*256) / 4`)
- Each growth copies the entire backing array — O(n)

### Preallocation

```go
users := make([]User, 0, len(ids))       // exact size known
results := make([]Result, 0, estimatedCount) // approximate size known
s = slices.Grow(s, additionalNeeded)      // pre-grow before bulk append (Go 1.21+)
```

### `slices` Package (Go 1.21+)

Key functions: `Sort`/`SortFunc`, `BinarySearch`, `Contains`, `Compact`, `Grow`. For `Clone`, `Equal`, `DeleteFunc` see go-safety.

## Map Internals

Maps are hash tables with 8-entry buckets and overflow chains. They are reference types — assigning a map copies the pointer, not the data.

```go
m := make(map[string]*User, len(users)) // avoids rehashing during population
```

### `maps` Package Quick Reference (Go 1.21+)

| Function | Purpose |
| --- | --- |
| `Collect` (1.23+) | Build map from iterator |
| `Insert` (1.23+) | Insert entries from iterator |
| `All` (1.23+) | Iterator over all entries |
| `Keys`, `Values` | Iterators over keys/values |

## Arrays

Fixed-size, value types. Copied entirely on assignment.

```go
type Digest [32]byte           // fixed-size, value type
var grid [3][3]int             // multi-dimensional
cache := map[[2]int]Result{}   // arrays are comparable — usable as map keys
```

Prefer slices for everything else — arrays cannot grow and pass by value (expensive for large sizes).

## container/ Standard Library

| Package | Data Structure | Best For |
| --- | --- | --- |
| `container/list` | Doubly-linked list | LRU caches, frequent middle insertion/removal |
| `container/heap` | Min-heap (priority queue) | Top-K, scheduling, Dijkstra |
| `container/ring` | Circular buffer | Rolling windows, round-robin |
| `bufio` | Buffered reader/writer/scanner | Efficient I/O with small reads/writes |

Container types use `any` (no type safety) — consider generic wrappers.

## strings.Builder vs bytes.Buffer

Use `strings.Builder` for pure string concatenation (avoids copy on `String()`), `bytes.Buffer` when you need `io.Reader` or byte manipulation. Both support `Grow(n)`.

## Generic Collections (Go 1.18+)

Use the tightest constraint possible. `comparable` for map keys, `cmp.Ordered` for sorting, custom interfaces for domain-specific ordering.

```go
type Set[T comparable] map[T]struct{}

func (s Set[T]) Add(v T)           { s[v] = struct{}{} }
func (s Set[T]) Contains(v T) bool { _, ok := s[v]; return ok }
```

## Pointer Types

| Type | Use Case | Zero Value |
| --- | --- | --- |
| `*T` | Normal indirection, mutation, optional values | `nil` |
| `unsafe.Pointer` | FFI, low-level memory layout (6 spec patterns only) | `nil` |
| `weak.Pointer[T]` (1.24+) | Caches, canonicalization, weak references | N/A |

## Copy Semantics Quick Reference

| Type | Copy Behavior | Independence |
| --- | --- | --- |
| `int`, `float`, `bool`, `string` | Value (deep copy) | Fully independent |
| `array`, `struct` | Value (deep copy) | Fully independent |
| `slice` | Header copied, backing array shared | Use `slices.Clone` |
| `map` | Reference copied | Use `maps.Clone` |
| `channel` | Reference copied | Same channel |
| `*T` (pointer) | Address copied | Same underlying value |
| `interface` | Value copied (type + value pair) | Depends on held type |

## Third-Party Libraries

For advanced data structures beyond the standard library: `emirpasic/gods` (trees, sets, lists, stacks, maps, queues), `deckarep/golang-set` (sets), `gammazero/deque` (double-ended queue).

## Common Mistakes

| Mistake | Fix |
| --- | --- |
| Growing a slice in a loop without preallocation | Each growth copies the entire backing array — O(n) per growth. Use `make([]T, 0, n)` or `slices.Grow` |
| Using `container/list` when a slice would suffice | Linked lists have poor cache locality. Benchmark first |
| `bytes.Buffer` for pure string building | Buffer's `String()` copies the underlying bytes. `strings.Builder` avoids this copy |
| `unsafe.Pointer` stored as `uintptr` across statements | GC can move the object between statements — the `uintptr` becomes a dangling reference |
| Large struct values in maps (copying overhead) | Map access copies the entire value. Use `map[K]*V` for large value types |

## References

- [Go Data Structures (Russ Cox)](https://research.swtch.com/godata)
- [The Go Memory Model](https://go.dev/ref/mem)

## Cross-References

- go-safety — nil map/slice pitfalls, append aliasing, defensive copying
- go-concurrency — channels, `sync.Map`, `sync.Pool`, sync primitives
- go-design-patterns — `string` vs `[]byte` vs `[]rune`, iterators, streaming
