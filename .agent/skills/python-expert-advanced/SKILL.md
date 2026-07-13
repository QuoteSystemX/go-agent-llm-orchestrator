---
name: python-expert-advanced
description: Advanced Python engineering — performance optimization, C-interop, deep concurrency, and memory management.
allowed-tools: Read, Write, Edit, Glob, Grep, Run
version: 1.0.0
---

# 🚀 Advanced Python Expert

> Deep-level engineering for high-scale Python systems.

---

## 1. Deep Concurrency (Asyncio 2026)

### TaskGroups (PEP 654)
Use `asyncio.TaskGroup` instead of `asyncio.gather` for robust error handling.
```python
async with asyncio.TaskGroup() as tg:
    tg.create_task(job1())
    tg.create_task(job2())
# Automatically waits and handles multiple exceptions
```

### Shared Memory & Multiprocessing
For CPU-bound tasks with large data:
- Use `multiprocessing.shared_memory`.
- Avoid serialization overhead (Pickle) between processes.

---

## 2. Performance & C-Interop

### Rust-in-Python (PyO3)
When Python is too slow:
1. Identify the bottleneck via `cProfile`.
2. Rewrite the core logic in Rust using `PyO3`.
3. Use `maturin` for seamless integration.

### Memory Optimization
- **`__slots__`**: Use to reduce memory footprint of large object sets.
- **`tracemalloc`**: Use for detecting memory leaks.
- **Weak References**: Use `weakref` to prevent reference cycles in complex graphs.

---

## 3. Metaprogramming & Internals

### Metaclasses vs Class Decorators
- Use **Class Decorators** for 90% of cases (simpler, faster).
- Use **Metaclasses** only when you need to control class *creation* and inheritance registry (e.g., ORM models).

### Custom Import Hooks
Use `importlib.abc.MetaPathFinder` for dynamic code generation or encrypted module loading.

---

## 4. Advanced Testing & Quality

### Property-Based Testing
Use `Hypothesis` to find edge cases that human-written tests miss.
```python
from hypothesis import given, strategies as st

@given(st.lists(st.integers()))
def test_sort(l):
    sorted_l = sorted(l)
    assert all(sorted_l[i] <= sorted_l[i+1] for i in range(len(sorted_l)-1))
```

---
## 4. Observability & Telemetry

### OpenTelemetry (OTel)
Always instrument your services for traces and metrics:
```python
from opentelemetry import trace
tracer = trace.get_tracer(__name__)

@tracer.start_as_current_span("heavy_task")
async def heavy_task():
    ...
```

### Structured Logging (Loki/Elastic)
Use `structlog` for machine-readable logs:
- Add `request_id` to every log entry.
- Log events, not just strings.

---

## 5. AI Foundations (Data Intensive)

### Vectorized Operations
- **`numpy` / `polars`**: Use Polars for large dataframes (it's faster than Pandas in 2026).
- **`tensor-converters`**: Efficiently move data between Python and GPU (PyTorch/Tensorflow).

### Local Model Serving
Integrate with `Ollama` or `vLLM` using specialized async clients.

---

## 🛠 Expert Scripts

| Script | Purpose |
|--------|---------|
| `memory_leak_detector.py` | Runs the app under `tracemalloc` and reports leaks. |
| `perf_benchmarker.py` | Micro-benchmarking using `timeit` and `pyperf`. |
| `ast_refactor_pro.py` | Structural refactoring using the `ast` module. |
| `otel_verify.py` | Verifies that spans are correctly propagated through the stack. |

---

## 📈 Decision Logic: When to go "Advanced"?
- **Scenario**: 1M+ RPS -> Use **Cython/Rust** for parsers.
- **Scenario**: 10GB+ RAM Usage -> Use **Shared Memory / Slots**.
- **Scenario**: Complex Plugin System -> Use **Metaprogramming**.

## When to Use

- **Optimizing slow Python code** — profile first, then
  optimize. Never guess.
- **Implementing concurrency** — asyncio for I/O-bound, threading
  for I/O-bound (with GIL), multiprocessing for CPU-bound.
- **Designing decorators, metaclasses, or descriptors** — for
  frameworks and libraries.
- **Type hints with mypy/pyright strict mode** — gradual typing
  for legacy codebases.
- **Memory profiling** — find leaks, optimize allocations.
- **Packaging complex libraries** — multi-package repos, C
  extensions, platform-specific wheels.

Avoid using this skill for:
- Simple scripts (just write them).
- Web development (use `@python-patterns` for idiomatic Python).
- Data analysis (use `@data-engineer`).

## Anti-Patterns

- **Don't use `asyncio` for CPU-bound work** — it serializes
  the work. Use `multiprocessing` or `concurrent.futures.ProcessPoolExecutor`.
- **Don't ignore the GIL** — threading is NOT parallelism for
  CPU work. Profile first.
- **Don't use mutable default arguments** — `def foo(x=[])` is
  a classic bug. Use `def foo(x=None): x = x or []`.
- **Don't mix `asyncio` and blocking I/O** — sync I/O in an async
  function blocks the event loop. Use `asyncio.to_thread`.
- **Don't skip type hints** — they catch bugs at static analysis
  time, before runtime. Use `mypy --strict`.
- **Don't catch bare `except:`** — it catches SystemExit and
  KeyboardInterrupt. Catch `Exception` instead.
- **Don't use `__slots__` everywhere** — it complicates
  inheritance. Use it only for memory-critical classes.

## Changelog

- **1.0.0** (2026-05-13): Initial version
