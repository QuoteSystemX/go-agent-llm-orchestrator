---
name: go-troubleshooting
description: Troubleshoot Go programs systematically — find and fix the root cause. Use when encountering bugs, crashes, deadlocks, or unexpected behavior in Go code. Covers debugging methodology, common Go pitfalls, test-driven debugging, pprof setup and capture, Delve debugger, race detection, GODEBUG tracing, and production debugging. Start here for any "something is wrong" situation. Not for interpreting profiles or benchmarking, or applying optimization patterns.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
version: 1.0.0
source: Adapted from samber/cc-skills-golang@golang-troubleshooting (MIT License) — https://github.com/samber/cc-skills-golang
---

# Go Troubleshooting Guide

**NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST.** Symptom fixes create new bugs and waste time — especially under time pressure.

## Quick Decision Tree

```
WHAT ARE YOU SEEING?

"Build won't compile"           → go build ./... 2>&1, go vet ./...
"Wrong output / logic bug"      → Write a failing test → check error handling, nil, off-by-one
"Random crashes / panics"       → GOTRACEBACK=all ./app → go test -race ./...
"Sometimes works, sometimes fails" → go test -race ./...
"Program hangs / frozen"        → curl localhost:6060/debug/pprof/goroutine?debug=2
"High CPU usage"                → pprof CPU profiling
"Memory growing over time"      → pprof heap profiling
"Slow / high latency / p99 spikes" → CPU + mutex + block profiles
"Simple bug, easy to reproduce" → Write a test, add fmt.Println / log.Debug
```

**Remember:** Read the Error → Reproduce → Measure One Thing → Fix → Verify

Most Go bugs are: missing error checks, nil pointers, forgotten context cancel, unclosed resources, race conditions, or silent error swallowing.

## The Golden Rules

### 1. Read the Error Message First

Go error messages are precise — file/line number, type mismatch, "undefined" (check imports/exported names/build tags), "cannot use X as Y" (check concrete types vs interfaces).

### 2. Reproduce Before You Fix

NEVER debug by guessing. Write a failing test, make it deterministic, isolate the minimal failing example, use `git bisect` to find the breaking commit.

### 3. If You Don't Measure It, You're Guessing

Never rely on intuition for performance or concurrency bugs: pprof over intuition, race detector over reasoning, benchmarks over assumptions.

### 4. One Hypothesis at a Time

Change one thing, measure, confirm. Changing three things at once teaches nothing.

### 5. Find the Root Cause — No Workarounds

A band-aid fix that masks the symptom IS NOT ACCEPTABLE. Trace the data flow backwards from the symptom to its origin. Question your assumptions. Ask "why" five times.

### 6. Research the Codebase, Not Just the Diff

Before flagging a bug or proposing a fix, trace the data flow and check for upstream handling — a function that looks broken in isolation may be correct in context (callers may validate inputs, middleware may enforce invariants). Trace callers, check upstream validation, read the surrounding code. When context reduces severity but doesn't eliminate the issue, still report it at reduced priority with a note on which upstream guarantees protect it.

### 7. Start Simple

`fmt.Println` IS the right tool for local debugging. Escalate only when simpler approaches fail. NEVER use `fmt.Println` for production debugging — use `slog`.

## Red Flags: You're Debugging Wrong

- **"Quick fix for now, investigate later"** — there is no "later". Find the root cause.
- **Multiple simultaneous changes** — one hypothesis at a time.
- **Proposing fixes without understanding the cause** — guessing is not debugging.
- **Each fix reveals a new problem** — you're treating symptoms.
- **3+ fix attempts on the same issue** — wrong mental model. Re-read the code, trace the data flow from scratch.
- **"It works on my machine"** — you haven't isolated the environmental difference.
- **Blaming the framework/stdlib/compiler** — it's almost never a Go bug. Verify your code first.

## Common Go Bugs

Nil pointer dereferences, interface nil gotcha (typed nil ≠ nil, see go-safety), variable shadowing, slice/map/defer/error/context pitfalls, race conditions, JSON unmarshaling surprises, unclosed resources.

## Concurrency Debugging

Race conditions, deadlocks, goroutine leaks. Use the race detector (`-race`) as the default tool. Detect leaks with `goleak` (see go-testing). Analyze stack dumps (`GOTRACEBACK=all`, `/debug/pprof/goroutine?debug=2`) for deadlock clues.

## Performance Troubleshooting

CPU profiling workflow, memory analysis (heap vs alloc_objects), lock contention (mutex profile), I/O blocking (goroutine profile). Read flamegraphs, identify hot functions, measure improvement with benchmarks — see go-performance-related guidance in go-patterns.

## pprof Quick Reference

```bash
# CPU profile
go tool pprof http://localhost:6060/debug/pprof/profile?seconds=30

# Heap profile
go tool pprof http://localhost:6060/debug/pprof/heap

# Goroutine dump
curl http://localhost:6060/debug/pprof/goroutine?debug=2
```

Enable pprof endpoints in production behind auth/network isolation, never exposed publicly.

## Diagnostic Tools

GODEBUG environment variables (GC tracing, scheduler tracing), Delve debugger for breakpoint debugging (`go install github.com/go-delve/delve/cmd/dlv@latest`), escape analysis (`go build -gcflags="-m -l"` to find unintended heap allocations), Go's execution tracer for goroutine scheduling.

## Production Debugging

Structure logs for searchability. Enable pprof safely (auth, network isolation). Capture profiles from running services. Network debugging (tcpdump, netstat). HTTP request/response inspection.

## Cross-References

- go-observability — metrics, alerting, and dashboards for Go runtime monitoring
- go-concurrency, go-safety, go-error-handling
