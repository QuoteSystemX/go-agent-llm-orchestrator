#!/usr/bin/env python3
"""Autonomous Fuzzer — Red Team Runtime Fuzzer.

Discovers Python functions via AST, generates mutated/invalid payloads,
executes them in sandbox_runner.py (isolated subprocess), and reports crashes.

Usage:
    python3 autonomous_fuzzer.py                          # fuzz all discovered functions
    python3 autonomous_fuzzer.py --target os.path.join    # fuzz specific function
    python3 autonomous_fuzzer.py --diff                   # fuzz only changed files (git)
    python3 autonomous_fuzzer.py --list                   # list discoverable functions

Exit codes:
    0 — all fuzz tests passed
    1 — crashes detected

Dependencies:
    .agent/scripts/chaos/sandbox_runner.py
"""

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    import sys
    from pathlib import Path
    SCRIPTS_DIR = Path(__file__).resolve().parents[1]
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.append(str(SCRIPTS_DIR))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev"]:
        d_path = str(SCRIPTS_DIR / domain)
        if d_path not in sys.path:
            sys.path.append(d_path)

import os

import sys

import ast

import json

import logging

import subprocess

import argparse

import random

import string

from pathlib import Path

from datetime import datetime

from lib.suppress import suppress

try:
    from lib.paths import REPO_ROOT, BUS_DIR
    from lib.common import save_json_atomic, get_timestamp
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]
    BUS_DIR = REPO_ROOT / ".agent" / "bus"

SANDBOX = Path(__file__).parent / "sandbox_runner.py"
FUZZ_METRICS = BUS_DIR / "fuzz_metrics.json"

# ── Payload Generators ──

def _payloads_boundary_ints():
    """Generate boundary integer values."""
    return [0, -1, 1, 2**31 - 1, -2**31, 2**63 - 1, -2**63, 2**64 - 1, -2**64,
            10**6, -10**6, 10**12, -10**12]

def _payloads_strings():
    """Generate boundary and malicious string values."""
    return [
        "",
        "\x00",
        "\x00\x00\x00",
        "\n" * 1000,
        "A" * 10**6,           # very long string
        "\\x00" * 1000,
        "%s" * 100,            # format string attempt
        "{0}" * 100,
        "../../../etc/passwd",
        "/dev/null",
        "|| true",
        "$(whoami)",
        "`id`",
    ]

def _payloads_sql():
    """Generate SQL injection payloads."""
    return [
        "' OR '1'='1",
        "' OR '1'='1' --",
        "' OR '1'='1' /*",
        "admin' --",
        "'; DROP TABLE users; --",
        "' UNION SELECT * FROM users; --",
        "' WAITFOR DELAY '00:00:05' --",
        "1; SELECT pg_sleep(5) --",
        "1 UNION SELECT @@version",
        "' OR 1=1; SELECT * FROM information_schema.tables; --",
    ]

def _payloads_binary():
    """Generate random binary and structured data payloads."""
    payloads = []
    # Random bytes encoded as hex strings (JSON-safe)
    for _ in range(5):
        raw = bytes(random.randint(0, 255) for _ in range(random.randint(1, 100)))
        payloads.append(raw.hex())
    # Random unicode (filter out surrogate chars that break JSON)
    for _ in range(3):
        chars = []
        for _ in range(random.randint(1, 50)):
            cp = random.randint(0x80, 0xFFFF)  # stay in BMP to avoid surrogates
            chars.append(chr(cp))
        payloads.append("".join(chars))
    return payloads

def _payloads_json():
    """Generate JSON/structured data bombs."""
    return [
        {"key": "value", "nested": {"deep": {"deeper": {"deepest": "x" * 10000}}}},
        {"a": [{"b": [{"c": [{} for _ in range(100)]}]}]},
        # Mixed types (all JSON-safe)
        [1, "string", None, {}, [], 1.0, True, False, [1, 2]],
        {str(i): i for i in range(1000)},  # wide dict
    ]

def _payloads_recursion():
    """Generate deeply nested structures to trigger RecursionError."""
    deep = []
    current = deep
    for _ in range(10000):
        current.append([])
        current = current[0]
    return [deep]

def _payloads_none_edge():
    """Generate None/edge-case values (all JSON-safe)."""
    return [None, True, False, float("inf"), float("-inf"), float("nan"),
            [], {}, []]


ALL_PAYLOAD_GENERATORS = [
    ("boundary_ints", _payloads_boundary_ints),
    ("strings", _payloads_strings),
    ("sql_injection", _payloads_sql),
    ("binary", _payloads_binary),
    ("json_bomb", _payloads_json),
    ("recursion", _payloads_recursion),
    ("none_edge", _payloads_none_edge),
]


# ── Function Discovery ──

def discover_functions(target_dirs: list = None) -> list:
    """Walk target directories, parse Python files with AST, discover function names.

    Returns list of dicts: {target: "module.function", file: "path", line: N}
    """
    if target_dirs is None:
        target_dirs = ["scripts"]  # relative to REPO_ROOT

    functions = []
    for rel_dir in target_dirs:
        search_path = REPO_ROOT / rel_dir
        if not search_path.exists():
            continue
        for pyfile in sorted(search_path.rglob("*.py")):
            if pyfile.name == "__init__.py":
                continue
            try:
                tree = ast.parse(pyfile.read_text(encoding="utf-8", errors="ignore"))
            except SyntaxError:
                continue

            # Compute module path relative to REPO_ROOT
            rel_path = pyfile.relative_to(REPO_ROOT)
            module_path = str(rel_path.with_suffix("")).replace("/", ".")

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Skip private/dunder methods
                    if node.name.startswith("_"):
                        continue
                    target = f"{module_path}.{node.name}"
                    functions.append({
                        "target": target,
                        "file": str(rel_path),
                        "line": node.lineno,
                        "name": node.name,
                    })
    return functions


def get_git_changed_files() -> list:
    """Get list of Python files changed in working tree vs HEAD."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=10
        )
        files = [f.strip() for f in result.stdout.splitlines() if f.strip().endswith(".py")]
        return [str(Path(f).parent) for f in set(files)]
    except Exception:
        return []


# ── Fuzzing Engine ──

def _make_json_safe(obj, max_depth: int = 50, _depth: int = 0) -> object:
    """Convert an object to a JSON-safe representation.

    Handles deeply nested structures, bytes, and other non-JSON types.
    """
    if _depth > max_depth:
        return f"<max_depth:{max_depth}>"
    if isinstance(obj, bytes):
        return obj.hex()
    if isinstance(obj, (set, frozenset)):
        return sorted(str(x) for x in obj)
    if isinstance(obj, (bytearray, range)):
        return list(obj)
    if isinstance(obj, complex):
        return str(obj)
    if isinstance(obj, dict):
        return {_make_json_safe(k, max_depth, _depth + 1):
                _make_json_safe(v, max_depth, _depth + 1)
                for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_json_safe(x, max_depth, _depth + 1) for x in obj]
    if isinstance(obj, float) and (obj != obj or obj == float("inf") or obj == float("-inf")):
        return str(obj)
    return obj


def run_fuzz_test(target: str, payload, timeout: int = 10) -> dict:
    """Run a single fuzz test via sandbox_runner.py subprocess.

    Returns parsed JSON result from sandbox.
    """
    safe_payload = _make_json_safe(payload)
    try:
        spec = json.dumps({"target": target, "payload": safe_payload, "timeout": timeout})
    except (TypeError, RecursionError, OverflowError) as e:
        return {"ok": False, "error": type(e).__name__, "crash": True,
                "traceback": f"Serialization failed: {e}", "duration_ms": 0.0}
    try:
        result = subprocess.run(
            [sys.executable, str(SANDBOX), spec],
            capture_output=True, text=True, timeout=timeout + 5
        )
        if result.stdout:
            return json.loads(result.stdout)
        return {"ok": False, "error": "NoOutput", "crash": True, "traceback": result.stderr[:500]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "SandboxTimeout", "crash": True, "traceback": "Subprocess timed out"}
    except json.JSONDecodeError as e:
        return {"ok": False, "error": "JSONParseError", "crash": True, "traceback": str(e)}
    except FileNotFoundError:
        return {"ok": False, "error": "SandboxNotFound", "crash": False,
                "traceback": f"sandbox_runner.py not found at {SANDBOX}"}


def run_fuzz(target: str, payloads: list, tag: str = "custom") -> list:
    """Run all payloads against a target function.

    Returns list of result dicts.
    """
    results = []
    for i, payload in enumerate(payloads):
        result = run_fuzz_test(target, payload)
        result["target"] = target
        result["payload_tag"] = tag
        result["payload_index"] = i
        results.append(result)

        # Print progress
        status = "💥 CRASH" if result.get("crash") else "✅ OK"
        dur = result.get("duration_ms", 0)
        print(f"  [{status}] {target} ({tag}#{i}) — {dur}ms")
        if result.get("crash"):
            err = result.get("error", "Unknown")
            tb = result.get("traceback", "")[:200]
            print(f"          ⛔ {err}: {tb}")

    return results


# ── Metrics ──

def _load_metrics() -> dict:
    """Load existing fuzz metrics or return empty structure."""
    if FUZZ_METRICS.exists():
        with suppress("autonomous_fuzzer.load_metrics", level=logging.WARNING):
            return json.loads(FUZZ_METRICS.read_text())
    return {"fuzz_runs": [], "summary": {"total_tests": 0, "total_crashes": 0}}


def _append_metrics(session: dict):
    """Append a fuzz session to metrics file."""
    metrics = _load_metrics()
    metrics["fuzz_runs"].append(session)
    total = metrics["summary"]["total_tests"] + session["tests_run"]
    crashes = metrics["summary"]["total_crashes"] + session["crashes"]
    metrics["summary"] = {"total_tests": total, "total_crashes": crashes,
                          "last_run": get_timestamp()}
    save_json_atomic(FUZZ_METRICS, metrics)


# ── Main ──

def main():
    parser = argparse.ArgumentParser(description="Autonomous Runtime Fuzzer (Red Team)")
    parser.add_argument("--target", help="Fuzz specific module.function")
    parser.add_argument("--list", action="store_true", help="List discoverable functions")
    parser.add_argument("--diff", action="store_true", help="Fuzz only git-changed files")
    parser.add_argument("--dirs", nargs="+", default=["scripts"],
                        help="Target directories relative to REPO_ROOT")
    parser.add_argument("--payloads", nargs="+", default=["all"],
                        choices=["all", "boundary_ints", "strings", "sql_injection", "binary", "json_bomb", "recursion", "none_edge"],
                        help="Payload category(ies) to use (e.g. --payloads strings boundary_ints)")
    parser.add_argument("--limit", type=int, default=0,
                        help="Max functions to fuzz (0 = all)")
    args = parser.parse_args()

    print("🧪 Autonomous Runtime Fuzzer (Red Team)")
    print("=" * 50)

    # ── List mode ──
    if args.list:
        print("\n🔍 Discovering functions...")
        functions = discover_functions(args.dirs)
        print(f"\nFound {len(functions)} discoverable functions:")
        for fn in sorted(functions, key=lambda x: x["target"]):
            print(f"  📍 {fn['target']}  ({fn['file']}:{fn['line']})")
        return

    # ── Determine targets ──
    if args.target:
        targets = [{"target": args.target, "file": "manual", "line": 0, "name": args.target.split(".")[-1]}]
        print(f"\n🎯 Target: {args.target}")
    elif args.diff:
        changed_dirs = get_git_changed_files()
        if not changed_dirs:
            print("\nℹ️  No changed Python files detected.")
            return
        print(f"\n📂 Git-changed dirs: {changed_dirs}")
        targets = discover_functions(changed_dirs)
    else:
        targets = discover_functions(args.dirs)

    if not targets:
        print("\n⚠️  No functions discovered for fuzzing.")
        return

    # Apply limit
    if args.limit > 0:
        targets = targets[:args.limit]

    print(f"\n🎯 Fuzzing {len(targets)} function(s)")

    # ── Select payload generators ──
    payload_gen_map = dict(ALL_PAYLOAD_GENERATORS)
    if "all" in args.payloads:
        generators = ALL_PAYLOAD_GENERATORS
    else:
        generators = []
        for name in args.payloads:
            if name in payload_gen_map:
                generators.append((name, payload_gen_map[name]))

    # ── Fuzz loop ──
    session = {
        "timestamp": get_timestamp(),
        "args": vars(args),
        "targets_count": len(targets),
        "tests_run": 0,
        "crashes": 0,
        "results": [],
    }

    for fn in targets:
        target = fn["target"]
        print(f"\n🔎 Fuzzing: {target}  ({fn['file']}:{fn['line']})")

        for tag_name, gen_func in generators:
            payloads = gen_func()
            results = run_fuzz(target, payloads, tag=tag_name)
            session["results"].extend(results)
            session["tests_run"] += len(results)
            session["crashes"] += sum(1 for r in results if r.get("crash"))

    # ── Summary ──
    print("\n" + "=" * 50)
    print(f"📊 Fuzz Session Complete")
    print(f"   Tests run: {session['tests_run']}")
    print(f"   Crashes:   {session['crashes']}")
    if session["crashes"]:
        print("   ⛔ CRASHES DETECTED — investigate results")
    else:
        print("   ✅ No crashes detected")

    # ── Save metrics ──
    _append_metrics(session)
    print(f"\n📝 Metrics saved to: {FUZZ_METRICS}")

    # Exit code 1 if crashes found
    if session["crashes"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
