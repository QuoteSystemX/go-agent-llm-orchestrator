---
name: go-samber-ro
description: Reactive streams and event-driven programming in Go using samber/ro — ReactiveX implementation with 150+ type-safe operators, cold/hot observables, 5 subject types, declarative pipelines via Pipe, 40+ plugins (HTTP, cron, fsnotify, JSON, logging), automatic backpressure, error propagation, and Go context integration. Apply when building asynchronous event-driven pipelines, real-time data processing, or reactive architectures in Go. Not for finite slice transforms (see go-samber-lo).
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
version: 1.0.0
source: Adapted from samber/cc-skills-golang@golang-samber-ro (MIT License) — https://github.com/samber/cc-skills-golang
---

# samber/ro — Reactive Streams for Go

Go implementation of [ReactiveX](https://reactivex.io/). Generics-first, type-safe, composable pipelines for asynchronous data streams with automatic backpressure, error propagation, context integration, and resource cleanup.

**Official Resources:** [github.com/samber/ro](https://github.com/samber/ro) · [ro.samber.dev](https://ro.samber.dev)

## Why samber/ro (Streams vs Slices)

Go channels + goroutines become unwieldy for complex async pipelines. `samber/ro` solves this with declarative, chainable stream operators.

| Scenario | Tool | Why |
| --- | --- | --- |
| Transform a slice (map, filter, reduce) | `samber/lo` | Finite, synchronous, eager — no stream overhead needed |
| Simple goroutine fan-out with error handling | `errgroup` | Standard lib, lightweight, sufficient for bounded concurrency |
| Infinite event stream (WebSocket, tickers, file watcher) | `samber/ro` | Declarative pipeline with backpressure, retry, timeout, combine |
| Real-time data enrichment from multiple async sources | `samber/ro` | CombineLatest/Zip compose dependent streams without manual select |
| Pub/sub with multiple consumers sharing one source | `samber/ro` | Hot observables (Share/Subjects) handle multicast natively |

| Aspect | `samber/lo` | `samber/ro` |
| --- | --- | --- |
| Data | Finite slices | Infinite streams |
| Execution | Synchronous, blocking | Asynchronous, non-blocking |
| Evaluation | Eager | Lazy |
| Error model | Return `(T, error)` per call | Error channel propagates through pipeline |

## Installation

```bash
go get github.com/samber/ro
```

## Core Concepts

1. **Observable** — a data source that emits values over time. Cold by default: each subscriber triggers independent execution
2. **Observer** — a consumer with three callbacks: `onNext(T)`, `onError(error)`, `onComplete()`
3. **Operator** — a function that transforms an observable into another, chained via `Pipe`
4. **Subscription** — the connection between observable and observer

```go
observable := ro.Pipe2(
    ro.RangeWithInterval(0, 5, 1*time.Second),
    ro.Filter(func(x int) bool { return x%2 == 0 }),
    ro.Map(func(x int) string { return fmt.Sprintf("even-%d", x) }),
)

observable.Subscribe(ro.NewObserver(
    func(s string) { fmt.Println(s) },
    func(err error) { log.Println(err) },
    func() { fmt.Println("Done!") },
))

// Or collect synchronously:
values, err := ro.Collect(observable)
```

## Cold vs Hot Observables

**Cold** (default): each `.Subscribe()` starts a new independent execution — safe and predictable. **Hot**: multiple subscribers share a single execution — use when the source is expensive (WebSocket, DB poll) or subscribers must see the same events.

| Convert with | Behavior |
| --- | --- |
| `Share()` | Cold → hot with reference counting |
| `ShareReplay(n)` | Same as Share + buffers last N values for late subscribers |
| `Connectable()` | Cold → hot, but waits for explicit `.Connect()` |

| Subject | Constructor | Replay behavior |
| --- | --- | --- |
| `PublishSubject` | `NewPublishSubject[T]()` | None — late subscribers miss past events |
| `BehaviorSubject` | `NewBehaviorSubject[T](initial)` | Replays last value to new subscribers |
| `ReplaySubject` | `NewReplaySubject[T](bufferSize)` | Replays last N values |
| `AsyncSubject` | `NewAsyncSubject[T]()` | Emits only last value, only on complete |
| `UnicastSubject` | `NewUnicastSubject[T](bufferSize)` | Single subscriber only |

## Operator Quick Reference

| Category | Key operators | Purpose |
| --- | --- | --- |
| Creation | `Just`, `FromSlice`, `FromChannel`, `Range`, `Interval`, `Defer`, `Future` | Create observables |
| Transform | `Map`, `MapErr`, `FlatMap`, `Scan`, `Reduce`, `GroupBy` | Transform or accumulate |
| Filter | `Filter`, `Take`, `TakeLast`, `Skip`, `Distinct`, `Find`, `First`, `Last` | Selectively emit |
| Combine | `Merge`, `Concat`, `Zip2`–`Zip6`, `CombineLatest2`–`5`, `Race` | Merge multiple observables |
| Error | `Catch`, `OnErrorReturn`, `OnErrorResumeNextWith`, `Retry`, `RetryWithConfig` | Recover from errors |
| Timing | `Delay`, `DelayEach`, `Timeout`, `ThrottleTime`, `SampleTime`, `BufferWithTime` | Control emission timing |
| Side effect | `Tap`/`Do`, `TapOnNext`, `TapOnError`, `TapOnComplete` | Observe without altering stream |
| Terminal | `Collect`, `ToSlice`, `ToChannel`, `ToMap` | Consume stream into Go types |

Use typed `Pipe2`, `Pipe3`...`Pipe25` for compile-time type safety across operator chains. The untyped `Pipe` uses `any` and loses type checking.

## Common Mistakes

| Mistake | Why it fails | Fix |
| --- | --- | --- |
| Using `ro.OnNext()` without error handler | Errors silently dropped — bugs hide in production | Use `ro.NewObserver(onNext, onError, onComplete)` with all 3 callbacks |
| Using untyped `Pipe()` instead of `Pipe2`/`Pipe3` | Loses compile-time type safety | Use typed `PipeN` functions |
| Forgetting `.Unsubscribe()` on infinite streams | Goroutine leak — runs forever | Use `TakeUntil(signal)`, context cancellation, or explicit `Unsubscribe()` |
| Using `Share()` when cold is sufficient | Unnecessary complexity | Use hot observables only when multiple consumers need the same stream |
| Using `samber/ro` for finite slice transforms | Stream overhead for a synchronous operation | Use `samber/lo` instead |
| Not propagating context for cancellation | Streams ignore shutdown signals, resource leaks | Chain `ContextWithTimeout` or `ThrowOnContextCancel` |

## Best Practices

1. **Always handle all three events** — use `NewObserver(onNext, onError, onComplete)`, not just `OnNext`
2. **Use `Collect()` for synchronous consumption** — when the stream is finite and you need `[]T`
3. **Prefer typed Pipe functions** — `Pipe2`...`Pipe25` catch type mismatches at compile time
4. **Bound infinite streams** — use `Take(n)`, `TakeUntil(signal)`, `Timeout(d)`, or context cancellation
5. **Use `Tap`/`Do` for observability** — log, trace, or meter emissions without altering the stream
6. **Prefer `samber/lo` for simple transforms** — reach for `ro` when data arrives over time or needs retry/timeout/backpressure

## Plugin Ecosystem

40+ plugins: encoding (JSON, CSV, Base64), network (HTTP, I/O, FSNotify), scheduling (Cron, ICS), observability (Zap, Slog, Zerolog, Sentry, Oops), rate limiting, system (Process, Signal).

If you encounter a bug in samber/ro, open an issue at [github.com/samber/ro/issues](https://github.com/samber/ro/issues).

## Cross-References

- go-samber-lo — finite slice transforms — use lo when data is already in a slice
- go-samber-mo — monadic types that compose with ro pipelines
- go-samber-hot — in-memory caching (also available as an ro plugin)
- go-concurrency — goroutine/channel patterns when reactive streams are overkill
