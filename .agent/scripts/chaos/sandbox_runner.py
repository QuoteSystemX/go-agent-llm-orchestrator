#!/usr/bin/env python3
"""Sandbox Runner — Isolated subprocess execution for fuzzing.

Called by autonomous_fuzzer.py as a subprocess.
Sets resource limits (RAM, CPU, file size) and executes a target
Python function with a given payload in complete isolation.

Usage (subprocess):
    python3 sandbox_runner.py '{"target": "os.path.join", "payload": "..."}'

Returns JSON to stdout:
    {"ok": true, "result": ..., "duration_ms": 12}
    {"ok": false, "error": "TypeError", "traceback": "...", "crash": true}
    Optionally includes "warnings": [...] if any non-critical resource limits
    could not be applied (e.g. RLIMIT_STACK on restricted platforms).
"""

import sys
import json
import resource
import signal
import traceback
import importlib
import time
import os
import tempfile
import subprocess as _sp
from pathlib import Path

# ── Resource probe & limits ──

def _parse_size(val: str) -> int:
    """Parse human-readable size: '512M', '2G', '1048576' → bytes."""
    val = val.strip().upper()
    suffixes = {"K": 1024, "M": 1024 ** 2, "G": 1024 ** 3}
    for suffix, mult in suffixes.items():
        if val.endswith(suffix):
            try:
                return int(float(val[:-1]) * mult)
            except ValueError:
                break
    return int(float(val))


def _probe_resources() -> dict:
    """Auto-detect system resources and compute safe sandbox limits.

    Order of precedence:
      1. Env var override (SANDBOX_MAX_RAM, _CPU, _STACK, _FSIZE)
      2. System auto-detect (total RAM, system stack limit)
      3. Sensible fallback defaults
    """
    # ── RAM: detect total physical memory ──
    total_ram = 2 * 1024 ** 3  # fallback: 2 GB
    try:
        if sys.platform == "darwin":
            out = _sp.run(["sysctl", "-n", "hw.memsize"],
                          capture_output=True, text=True, timeout=3)
            if out.returncode == 0:
                total_ram = int(out.stdout.strip())
        elif sys.platform.startswith("linux"):
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        total_ram = int(line.split()[1]) * 1024  # kB → bytes
                        break
    except Exception:
        pass

    # 20% of total RAM, clamped [64 MB, 4 GB]
    max_ram = max(64 * 1024 ** 2, min(total_ram // 5, 4 * 1024 ** 3))

    # ── Stack: inherit from system rlimit ──
    try:
        soft, _ = resource.getrlimit(resource.RLIMIT_STACK)
        if soft == resource.RLIM_INFINITY:
            max_stack = 8 * 1024 ** 2   # fallback
        else:
            max_stack = int(soft * 0.8)  # 80% of system limit
    except Exception:
        max_stack = 8 * 1024 ** 2
    max_stack = max(256 * 1024, min(max_stack, 64 * 1024 ** 2))  # [256 KB, 64 MB]

    # ── Env overrides (highest precedence) ──
    if os.environ.get("SANDBOX_MAX_RAM"):
        max_ram = _parse_size(os.environ["SANDBOX_MAX_RAM"])

    max_cpu = int(os.environ.get("SANDBOX_MAX_CPU", "5"))

    if os.environ.get("SANDBOX_MAX_STACK"):
        max_stack = _parse_size(os.environ["SANDBOX_MAX_STACK"])

    max_fsize = _parse_size(os.environ.get("SANDBOX_MAX_FSIZE", "10M"))

    return {
        "max_ram": max_ram,
        "max_cpu": max_cpu,
        "max_stack": max_stack,
        "max_fsize": max_fsize,
    }


# Probe once at module load
_RESOURCES = _probe_resources()
MAX_RAM = _RESOURCES["max_ram"]
MAX_CPU = _RESOURCES["max_cpu"]
MAX_STACK = _RESOURCES["max_stack"]
MAX_FSIZE = _RESOURCES["max_fsize"]


def _apply_limits() -> list:
    """Apply resource limits to the current process.

    CRITICAL limits (AS/RAM, CPU): must succeed or sandbox refuses to start.
    OPTIONAL limits (STACK, FSIZE): best-effort, failures are collected as warnings.
    Verification: reads back critical limits via getrlimit() to confirm they are active.

    Returns:
        list[str]: Warnings for any optional limits that were not applied.

    Raises:
        RuntimeError: If any critical limit (AS, CPU) could not be applied or verified.
    """
    warnings = []

    # ── Critical limits: fail-fast on failure ──
    try:
        resource.setrlimit(resource.RLIMIT_AS, (MAX_RAM, MAX_RAM))
        resource.setrlimit(resource.RLIMIT_CPU, (MAX_CPU, MAX_CPU + 1))
    except Exception as e:
        raise RuntimeError(
            f"Sandbox CRITICAL resource limit failed to apply: {e}"
        ) from e

    # ── Optional limits: best-effort ──
    for rlimit, value, name in [
        (resource.RLIMIT_STACK, (MAX_STACK, MAX_STACK), "STACK"),
        (resource.RLIMIT_FSIZE, (MAX_FSIZE, MAX_FSIZE), "FSIZE"),
    ]:
        try:
            resource.setrlimit(rlimit, value)
        except Exception as e:
            warnings.append(f"RLIMIT_{name} could not be applied: {e}")

    # ── Verification: confirm critical limits are active ──
    for rlimit, expected, name in [
        (resource.RLIMIT_AS, MAX_RAM, "AS"),
        (resource.RLIMIT_CPU, (MAX_CPU, MAX_CPU + 1), "CPU"),
    ]:
        try:
            soft, _ = resource.getrlimit(rlimit)
            exp = expected[0] if isinstance(expected, tuple) else expected
            if soft != exp:
                raise RuntimeError(
                    f"Sandbox RLIMIT_{name} verification failed: "
                    f"requested {exp}, active {soft}"
                )
        except RuntimeError:
            raise
        except Exception as e:
            warnings.append(f"RLIMIT_{name} verification could not be read: {e}")

    if os.environ.get("SANDBOX_DEBUG"):
        parts = [f"[sandbox] RAM={MAX_RAM//1024**2}M CPU={MAX_CPU}s "
                 f"STACK={MAX_STACK//1024**2}M FSIZE={MAX_FSIZE//1024**2}M"]
        if warnings:
            parts.append(f"[WARNINGS: {'; '.join(warnings)}]")
        print(" ".join(parts), file=sys.stderr)

    return warnings


def _discover_repo_root() -> Path:
    """Find the repo root by walking up from cwd looking for .git."""
    cwd = Path(os.getcwd()).resolve()
    for parent in [cwd] + list(cwd.parents):
        if (parent / ".git").exists():
            return parent
    return cwd


def _resolve_target(target: str):
    """Parse 'module.function' and resolve import path.

    Returns (importable_module_name, function_name).

    Uses prefix-based mapping to resolve dotted paths:
      - os.path.join                         → direct import
      - .agent.scripts.lib.common.fn         → add REPO_ROOT/.agent/scripts/ to sys.path, import lib.common
    """
    parts = target.rsplit(".", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid target '{target}'. Use format: module.function")
    module_path, func_name = parts

    # --- Fast path: direct import (skip relative paths starting with '.') ---
    if not module_path.startswith("."):
        try:
            importlib.import_module(module_path)
            return module_path, func_name
        except ModuleNotFoundError:
            pass

    # --- Slow path: prefix-based resolution ---
    repo_root = _discover_repo_root()

    # Each entry: (prefix, sys.path_subdir, skip_chars)
    # When module_path starts with prefix, add repo_root/subdir to sys.path
    # and use module_path[skip_chars:] as the import name
    prefix_map = [
        (".agent.scripts.", ".agent/scripts", len(".agent.scripts.")),  # → lib.common
        (".agent.", ".", len(".agent.")),                                # → scripts.lib.common
    ]

    for prefix, subdir, skip in prefix_map:
        if module_path.startswith(prefix):
            sys_path_dir = str(repo_root / subdir)
            if sys_path_dir not in sys.path:
                sys.path.insert(0, sys_path_dir)

            import_name = module_path[skip:]  # e.g. "lib.common"
            try:
                importlib.import_module(import_name)
                return import_name, func_name
            except ModuleNotFoundError:
                # File might not exist — try next prefix
                continue

    raise ModuleNotFoundError(f"Could not resolve module '{module_path}' in any path. "
                              "Try: .agent.scripts.<module>.<func> or a direct stdlib path.")


def _execute(target: str, payload, timeout: int = 10):
    """Import module, call function with payload, return result."""
    module_path, func_name = _resolve_target(target)

    mod = importlib.import_module(module_path)

    # Get the function
    if not hasattr(mod, func_name):
        raise AttributeError(f"Module '{module_path}' has no function '{func_name}'")

    func = getattr(mod, func_name)

    # Call with payload as positional arg
    if isinstance(payload, list):
        result = func(*payload)
    elif isinstance(payload, dict):
        result = func(**payload)
    else:
        result = func(payload)

    return result


def run_sandboxed(spec: dict) -> dict:
    """Execute a single fuzz test in the sandbox.

    spec keys:
        - target: str — "module.function"
        - payload: any — argument to pass
        - timeout: int — max seconds (default 10)

    Returns dict with ok/error/duration.
    """
    target = spec["target"]
    payload = spec.get("payload", None)
    timeout = spec.get("timeout", 10)

    warnings = _apply_limits()

    start = time.monotonic()
    try:
        # Set alarm for timeout (SIGALRM may not work on Windows/macOS)
        signal.signal(signal.SIGALRM, lambda s, f: (_ for _ in ()).throw(TimeoutError("Sandbox timed out")))
        signal.alarm(timeout)

        result = _execute(target, payload, timeout)

        signal.alarm(0)  # Cancel alarm
        elapsed = (time.monotonic() - start) * 1000

        ret = {"ok": True, "result": repr(result)[:500], "duration_ms": round(elapsed, 1)}
        if warnings:
            ret["warnings"] = warnings
        return ret

    except MemoryError:
        ret = {"ok": False, "error": "MemoryError", "crash": True,
               "duration_ms": round((time.monotonic() - start) * 1000, 1),
               "traceback": "Out of memory (RLIMIT_AS exceeded)"}
        if warnings:
            ret["warnings"] = warnings
        return ret
    except TimeoutError:
        ret = {"ok": False, "error": "Timeout", "crash": True,
               "duration_ms": round((time.monotonic() - start) * 1000, 1),
               "traceback": f"CPU time exceeded {timeout}s limit"}
        if warnings:
            ret["warnings"] = warnings
        return ret
    except RecursionError:
        ret = {"ok": False, "error": "RecursionError", "crash": True,
               "duration_ms": round((time.monotonic() - start) * 1000, 1),
               "traceback": "Maximum recursion depth exceeded"}
        if warnings:
            ret["warnings"] = warnings
        return ret
    except Exception as e:
        tb = traceback.format_exc()
        elapsed = (time.monotonic() - start) * 1000
        ret = {"ok": False, "error": type(e).__name__, "crash": True,
               "duration_ms": round(elapsed, 1), "traceback": tb[-2000:]}
        if warnings:
            ret["warnings"] = warnings
        return ret
    finally:
        signal.alarm(0)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        spec_str = sys.stdin.read()
    else:
        spec_str = sys.argv[1]

    try:
        spec = json.loads(spec_str)
    except json.JSONDecodeError as e:
        result = {"ok": False, "error": "JSONParseError", "crash": False,
                  "traceback": str(e)}
        print(json.dumps(result))
        sys.exit(0)

    result = run_sandboxed(spec)
    print(json.dumps(result))

    if result.get("crash"):
        sys.exit(1)
