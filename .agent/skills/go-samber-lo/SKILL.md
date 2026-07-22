---
name: go-samber-lo
description: Functional programming helpers for Go using samber/lo — 500+ type-safe generic functions for slices, maps, channels, strings, math, tuples, and concurrency (Map, Filter, Reduce, GroupBy, Chunk, Flatten, Find, Uniq, etc). Core immutable package (lo), concurrent variants (lo/parallel aka lop), in-place mutations (lo/mutable aka lom), lazy iterators (lo/it aka loi for Go 1.23+). Apply when using or adopting samber/lo, when the codebase imports github.com/samber/lo, or when implementing functional-style data transformations in Go. Not for streaming pipelines (see go-samber-ro).
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
version: 1.0.0
source: Adapted from samber/cc-skills-golang@golang-samber-lo (MIT License) — https://github.com/samber/cc-skills-golang
---

# samber/lo — Functional Utilities for Go

Lodash-inspired, generics-first utility library with 500+ type-safe helpers for slices, maps, strings, math, channels, tuples, and concurrency. Zero external dependencies. Immutable by default.

**Official Resources:** [github.com/samber/lo](https://github.com/samber/lo) · [lo.samber.dev](https://lo.samber.dev) · [pkg.go.dev/github.com/samber/lo](https://pkg.go.dev/github.com/samber/lo)

## Why samber/lo

Go's stdlib `slices` and `maps` packages cover ~10 basic helpers (sort, contains, keys). Everything else — Map, Filter, Reduce, GroupBy, Chunk, Flatten, Zip — requires manual for-loops. `lo` fills this gap:

- **Type-safe generics** — no `interface{}` casts, no reflection
- **Immutable by default** — returns new collections, safe for concurrent reads
- **Composable** — functions take and return slices/maps, so they chain
- **Zero dependencies** — only Go stdlib
- **Progressive complexity** — start with `lo`, upgrade to `lop`/`lom`/`loi` only when profiling demands it
- **Error variants** — most functions have `Err` suffixes (`MapErr`, `FilterErr`, `ReduceErr`) that stop on first error

## Installation

```bash
go get github.com/samber/lo
```

| Package | Import | Alias | Go version |
| --- | --- | --- | --- |
| Core (immutable) | `github.com/samber/lo` | `lo` | 1.18+ |
| Parallel | `github.com/samber/lo/parallel` | `lop` | 1.18+ |
| Mutable | `github.com/samber/lo/mutable` | `lom` | 1.18+ |
| Iterator | `github.com/samber/lo/it` | `loi` | 1.23+ |

## Choose the Right Package

Start with `lo`. Move to other packages only when profiling shows a bottleneck or lazy evaluation is explicitly needed.

| Package | Use when | Trade-off |
| --- | --- | --- |
| `lo` | Default for all transforms | Allocates new collections (safe, predictable) |
| `lop` | CPU-bound work on large datasets (1000+ items) | Goroutine overhead; not for I/O or small slices |
| `lom` | Hot path confirmed by `pprof -alloc_objects` | Mutates input — caller must understand side effects |
| `loi` | Large datasets with chained transforms (Go 1.23+) | Lazy evaluation saves memory but adds iterator complexity |

**Key rules:** `lop` is for CPU parallelism, not I/O concurrency — for I/O fan-out, use `errgroup` instead (see go-concurrency). `lom` breaks immutability — only use when allocation pressure is measured, never assumed. For reactive/streaming pipelines over infinite event streams, see go-samber-ro.

## Core Patterns

```go
// Transform a slice
names := lo.Map(users, func(u User, _ int) string {
    return u.Name
})

// Filter + Reduce
total := lo.Reduce(
    lo.Filter(orders, func(o Order, _ int) bool { return o.Status == "paid" }),
    func(sum float64, o Order, _ int) float64 { return sum + o.Amount },
    0,
)

// GroupBy
byStatus := lo.GroupBy(tasks, func(t Task, _ int) string { return t.Status })
// map[string][]Task{"open": [...], "closed": [...]}

// Error variant — stop on first error
results, err := lo.MapErr(urls, func(url string, _ int) (Response, error) {
    return http.Get(url)
})
```

## Common Mistakes

| Mistake | Why it fails | Fix |
| --- | --- | --- |
| Using `lo.Contains` when `slices.Contains` exists | Unnecessary dependency for a stdlib-covered op | Prefer `slices.Contains`/`slices.Sort` (Go 1.21+) |
| Using `lop.Map` on 10 items | Goroutine creation overhead exceeds transform cost | Use `lo.Map` — `lop` benefits start at ~1000+ items |
| Assuming `lo.Filter` modifies the input | `lo` is immutable by default | Use `lom.Filter` for explicit in-place mutation |
| Using `lo.Must` in production code paths | `Must` panics on error | Use the non-Must variant and handle the error |
| Chaining many eager transforms on large data | Each step allocates an intermediate slice | Use `loi` (lazy iterators) |

## Best Practices

1. **Prefer stdlib when available** — `slices.Contains`/`slices.Sort` (1.21+) carry no dependency; use `lo` for transforms the stdlib doesn't offer
2. **Compose lo functions** — chain `Filter → Map → GroupBy` instead of nested loops
3. **Profile before optimizing** — switch from `lo` to `lom`/`lop` only after `pprof` confirms the bottleneck
4. **Use error variants** — prefer `lo.MapErr` over `lo.Map` + manual error collection
5. **Use `lo.Must` only in tests and init**

## Quick Reference

| Function | What it does |
| --- | --- |
| `lo.Map` | Transform each element |
| `lo.Filter` / `lo.Reject` | Keep / remove elements matching predicate |
| `lo.Reduce` | Fold elements into a single value |
| `lo.GroupBy` | Group elements by key |
| `lo.Chunk` | Split into fixed-size batches |
| `lo.Flatten` | Flatten nested slices one level |
| `lo.Uniq` / `lo.UniqBy` | Remove duplicates |
| `lo.Find` / `lo.FindOrElse` | First match or default |
| `lo.Contains` / `lo.Every` / `lo.Some` | Membership tests |
| `lo.Keys` / `lo.Values` | Extract map keys or values |
| `lo.Zip2` / `lo.Unzip2` | Pair/unpair two slices |
| `lo.Ternary` / `lo.If` | Inline conditionals |
| `lo.ToPtr` / `lo.FromPtr` | Pointer helpers |
| `lo.Must` / `lo.Try` | Panic-on-error / recover-as-bool |
| `lo.Debounce` / `lo.Throttle` | Rate limiting |

This skill is not exhaustive — refer to library documentation for the full 500+ function catalog. If you encounter a bug in samber/lo, open an issue at [github.com/samber/lo/issues](https://github.com/samber/lo/issues).

## Cross-References

- go-samber-ro — reactive/streaming pipelines over infinite event streams
- go-samber-mo — monadic types (Option, Result, Either) that compose with lo transforms
- go-data-structures — choosing the right underlying data structure
