---
name: go-samber-hot
description: In-memory caching in Go using samber/hot — eviction algorithms (LRU, LFU, TinyLFU, W-TinyLFU, S3FIFO, ARC, TwoQueue, SIEVE, FIFO), TTL, cache loaders, sharding, stale-while-revalidate, missing key caching, and Prometheus metrics. Apply when using or adopting samber/hot, when the codebase imports github.com/samber/hot, or when the project repeatedly loads the same medium-to-low cardinality resources at high frequency and needs to reduce latency or backend pressure.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
version: 1.0.0
source: Adapted from samber/cc-skills-golang@golang-samber-hot (MIT License) — https://github.com/samber/cc-skills-golang
---

# Using samber/hot for In-Memory Caching in Go

Generic, type-safe in-memory caching library for Go 1.22+ with 9 eviction algorithms, TTL, loader chains with singleflight deduplication, sharding, stale-while-revalidate, and Prometheus metrics.

**Official Resources:** [pkg.go.dev/github.com/samber/hot](https://pkg.go.dev/github.com/samber/hot) · [github.com/samber/hot](https://github.com/samber/hot)

```bash
go get -u github.com/samber/hot
```

## Algorithm Selection

Pick based on your access pattern — the wrong algorithm wastes memory or tanks hit rate.

| Algorithm | Constant | Best for | Avoid when |
| --- | --- | --- | --- |
| **W-TinyLFU** | `hot.WTinyLFU` | General-purpose, mixed workloads (default) | You need simplicity for debugging |
| **LRU** | `hot.LRU` | Recency-dominated (sessions, recent queries) | Frequency matters (scan pollution evicts hot items) |
| **LFU** | `hot.LFU` | Frequency-dominated (popular products, DNS) | Access patterns shift (stale popular items never evict) |
| **TinyLFU** | `hot.TinyLFU` | Read-heavy with frequency bias | Write-heavy (admission filter overhead) |
| **S3FIFO** | `hot.S3FIFO` | High throughput, scan-resistant | Small caches (<1000 items) |
| **ARC** | `hot.ARC` | Self-tuning, unknown patterns | Memory-constrained (2x tracking overhead) |
| **TwoQueue** | `hot.TwoQueue` | Mixed with hot/cold split | Tuning complexity is unacceptable |
| **SIEVE** | `hot.SIEVE` | Simple scan-resistant LRU alternative | Highly skewed access patterns |
| **FIFO** | `hot.FIFO` | Simple, predictable eviction order | Hit rate matters |

**Decision shortcut:** Start with `hot.WTinyLFU`. Switch only when profiling shows the miss rate is too high for your SLO.

## Core Usage

```go
import "github.com/samber/hot"

cache := hot.NewHotCache[string, *User](hot.WTinyLFU, 10_000).
    WithTTL(5 * time.Minute).
    WithJanitor().
    Build()
defer cache.StopJanitor()

cache.Set("user:123", user)
cache.SetWithTTL("session:abc", session, 30*time.Minute)
value, found, err := cache.Get("user:123")
```

### Loader Pattern (Read-Through)

Loaders fetch missing keys automatically with singleflight deduplication:

```go
cache := hot.NewHotCache[int, *User](hot.WTinyLFU, 10_000).
    WithTTL(5 * time.Minute).
    WithLoaders(func(ids []int) (map[int]*User, error) {
        return db.GetUsersByIDs(ctx, ids) // batch query
    }).
    WithJanitor().
    Build()
defer cache.StopJanitor()

user, found, err := cache.Get(123) // triggers loader on miss
```

## Capacity Sizing

1. **Estimate single-item size** — struct size + heap-allocated fields + key size + ~100 bytes overhead
2. **Ask what memory budget** is dedicated to this cache in production
3. **Compute capacity** — `capacity = memoryBudget / estimatedItemSize`, round down for headroom

```
Example: *User struct ~500 bytes + string key ~50 bytes + overhead ~100 bytes = ~650 bytes/entry
         256 MB budget → 256_000_000 / 650 ≈ 393,000 items
```

If item size is unknown, measure it with a unit test allocating N items and checking `runtime.ReadMemStats` — guessing leads to OOM or wasted memory.

## Common Mistakes

1. **Forgetting `WithJanitor()`** — without it, expired entries stay in memory until the algorithm evicts them
2. **Calling `SetMissing()` without missing cache config** — panics at runtime; enable `WithMissingCache(algorithm, capacity)` first
3. **`WithoutLocking()` + `WithJanitor()`** — mutually exclusive, panics
4. **Oversized cache** — a cache holding everything is a map with overhead. Size to your working set (10-20% of total data)
5. **Ignoring loader errors** — `Get()` returns `(zero, false, err)` on loader failure; always check `err`, not just `found`

## Best Practices

1. Always set TTL — unbounded caches serve stale data indefinitely
2. Use `WithJitter(lambda, upperBound)` to spread expirations — without it, items created together expire together, causing thundering herd
3. Monitor with `WithPrometheusMetrics(cacheName)` — hit rate below 80% usually means undersized cache or wrong algorithm
4. Use `WithCopyOnRead(fn)` / `WithCopyOnWrite(fn)` for mutable values — without copies, callers mutate cached objects and corrupt shared state

If you encounter a bug in samber/hot, open an issue at <https://github.com/samber/hot/issues>.

## Cross-References

- go-database — query patterns that pair with cache loaders
- go-observability — Prometheus metrics integration and monitoring
