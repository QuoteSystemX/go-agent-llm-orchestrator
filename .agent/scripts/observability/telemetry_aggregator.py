#!/usr/bin/env python3
"""
telemetry_aggregator.py — B5: collect and aggregate kit telemetry.

Reads from:
  - .agent/bus/lesson_applied.jsonl (STORY-6 knowledge loop)
  - .agent/bus/inbox_acks.jsonl (STORY-2 INBOX acks)
  - .agent/bus/daemon_stop.jsonl (STORY-3.3 SIGTERM)
  - .agent/bus/otel_spans.jsonl (STORY-5 harness OTel spans, if present)
  - .agent/bus/knowledge_injections.json (STORY-6 current state)

Outputs structured JSON for dashboard consumption or programmatic analysis.

Usage:
    python3 .agent/scripts/observability/telemetry_aggregator.py
    python3 .agent/scripts/observability/telemetry_aggregator.py --window 24h
    python3 .agent/scripts/observability/telemetry_aggregator.py --json
"""
import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
BUS_DIR = REPO_ROOT / ".agent" / "bus"

# Event log files
EVENT_LOGS = {
    "lesson_applied": BUS_DIR / "lesson_applied.jsonl",
    "inbox_ack": BUS_DIR / "inbox_acks.jsonl",
    "daemon_stop": BUS_DIR / "daemon_stop.jsonl",
    "harness_invoke": BUS_DIR / "otel_spans.jsonl",
    "capability_denied": BUS_DIR / "capability_denied.jsonl",
    "distill_sentinel": BUS_DIR / ".distill_sentinel",
}


def _read_jsonl(path: Path, since: datetime) -> list[dict]:
    """Read JSONL events, filtering by timestamp."""
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        # Try to parse timestamp; skip if older than since
        ts_str = ev.get("ts") or ev.get("timestamp")
        if ts_str:
            try:
                # Normalize: "2026-07-11T10:00:00Z" → "2026-07-11T10:00:00+00:00"
                ts_norm = ts_str.replace("Z", "+00:00")
                ts = datetime.fromisoformat(ts_norm)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts < since:
                    continue
            except (ValueError, TypeError):
                pass  # no timestamp → include
        events.append(ev)
    return events


def _sentinel_age() -> dict:
    """Read the .distill_sentinel file and return its age info."""
    sentinel = EVENT_LOGS["distill_sentinel"]
    if not sentinel.exists():
        return {"exists": False}
    try:
        stat = sentinel.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        age_s = time.time() - stat.st_mtime
        return {
            "exists": True,
            "mtime": mtime.isoformat(),
            "age_seconds": round(age_s),
            "age_human": _humanize_duration(age_s),
        }
    except Exception as e:
        return {"exists": True, "error": str(e)}


def _humanize_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds / 60)}m"
    if seconds < 86400:
        return f"{int(seconds / 3600)}h"
    return f"{int(seconds / 86400)}d"


def _injection_index() -> dict:
    """Read current knowledge injections."""
    idx_path = BUS_DIR / "knowledge_injections.json"
    if not idx_path.exists():
        return {"total": 0, "by_scope": {}, "active": 0, "stale": 0}
    try:
        idx = json.loads(idx_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"error": "parse failed"}
    injections = idx.get("injections", [])
    now = datetime.now(timezone.utc)
    by_scope = Counter()
    active = 0
    stale = 0
    for inj in injections:
        scope = inj.get("scope", "global")
        by_scope[scope] += 1
        try:
            reg = datetime.fromisoformat(inj["registered_ts"].replace("Z", "+00:00"))
            ttl_days = inj.get("ttl_days", 30)
            expires = reg + timedelta(days=ttl_days)
            if expires > now:
                active += 1
            else:
                stale += 1
        except Exception:
            pass
    return {
        "total": len(injections),
        "by_scope": dict(by_scope),
        "active": active,
        "stale": stale,
    }


def _harness_stats(events: list[dict]) -> dict:
    """Aggregate harness invocation stats from OTel spans."""
    by_harness = Counter()
    by_exit_code = Counter()
    by_caller = Counter()
    durations = []
    violations_total = 0
    for ev in events:
        attrs = ev.get("attributes", {})
        name = attrs.get("harness.name", "unknown")
        by_harness[name] += 1
        exit_code = attrs.get("exit.code")
        if exit_code is not None:
            by_exit_code[str(exit_code)] += 1
        caller = attrs.get("caller.role", "unknown")
        by_caller[caller] += 1
        dur = attrs.get("duration.ms")
        if dur is not None:
            durations.append(dur)
        violations_total += attrs.get("sandbox.violations", 0)
    avg_duration = sum(durations) / len(durations) if durations else 0
    return {
        "total_invocations": len(events),
        "by_harness": dict(by_harness),
        "by_exit_code": dict(by_exit_code),
        "by_caller": dict(by_caller),
        "avg_duration_ms": round(avg_duration, 1),
        "sandbox_violations_total": violations_total,
    }


def _capability_denied_stats(events: list[dict]) -> dict:
    by_action = Counter()
    by_role = Counter()
    by_cap = Counter()
    for ev in events:
        by_action[ev.get("action", "unknown")] += 1
        by_role[ev.get("caller_role", "unknown")] += 1
        by_cap[ev.get("required_capability", "unknown")] += 1
    return {
        "total_denied": len(events),
        "by_action": dict(by_action),
        "by_role": dict(by_role),
        "by_cap": dict(by_cap),
    }


def _inbox_stats(events: list[dict]) -> dict:
    by_intent = Counter()
    by_actor = Counter()
    for ev in events:
        # ack events have entry_id but not intent; the original entry had intent
        # but we only log acks. For richer stats we'd cross-reference.
        by_actor[ev.get("acked_by", "unknown")] += 1
    return {
        "total_acks": len(events),
        "by_actor": dict(by_actor),
    }


def aggregate(window_hours: int = 24) -> dict:
    """Aggregate telemetry for the given window (in hours)."""
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=window_hours)

    sections = {
        "metadata": {
            "window_hours": window_hours,
            "since": since.isoformat(),
            "now": now.isoformat(),
            "bus_dir": str(BUS_DIR),
        },
        "distill_sentinel": _sentinel_age(),
        "knowledge_injections": _injection_index(),
    }

    # Aggregate event logs
    for name, path in EVENT_LOGS.items():
        if name == "distill_sentinel":
            continue  # handled above
        events = _read_jsonl(path, since)
        if name == "harness_invoke":
            sections["harness_invocations"] = _harness_stats(events)
        elif name == "capability_denied":
            sections["capability_denied"] = _capability_denied_stats(events)
        elif name == "inbox_ack":
            sections["inbox_acks"] = _inbox_stats(events)
        else:
            sections[name] = {
                "total": len(events),
                "sample": events[:3] if events else [],
            }

    return sections


def main() -> int:
    p = argparse.ArgumentParser(
        prog="telemetry_aggregator",
        description="B5: aggregate kit telemetry from .agent/bus/.",
    )
    p.add_argument("--window", default="24h", help="Time window (e.g., 24h, 7d, 30d)")
    p.add_argument("--json", action="store_true", help="JSON output (default: human-readable)")
    args = p.parse_args()

    # Parse window
    window_str = args.window.strip().lower()
    if window_str.endswith("h"):
        hours = int(window_str[:-1])
    elif window_str.endswith("d"):
        hours = int(window_str[:-1]) * 24
    else:
        try:
            hours = int(window_str)
        except ValueError:
            print(f"❌ Bad window: {args.window}", file=sys.stderr)
            return 2

    result = aggregate(window_hours=hours)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    else:
        # Human-readable summary
        m = result["metadata"]
        print(f"📊 Telemetry (last {m['window_hours']}h)")
        print(f"   Window: {m['since']} → {m['now']}")
        print()
        ds = result.get("distill_sentinel", {})
        if ds.get("exists"):
            print(f"🧠 Distill sentinel: {ds.get('age_human', '?')} ago (mtime: {ds.get('mtime', '?')})")
        else:
            print("🧠 Distill sentinel: NOT PRESENT (run archivist_trigger.py)")
        ki = result.get("knowledge_injections", {})
        print(f"📚 Knowledge injections: {ki.get('total', 0)} total "
              f"({ki.get('active', 0)} active, {ki.get('stale', 0)} stale)")
        if ki.get("by_scope"):
            for scope, n in ki["by_scope"].items():
                print(f"   - scope={scope}: {n}")
        print()
        hi = result.get("harness_invocations", {})
        if hi.get("total_invocations", 0) > 0:
            print(f"🔧 Harness invocations: {hi['total_invocations']} "
                  f"(avg {hi['avg_duration_ms']}ms, {hi['sandbox_violations_total']} violations)")
            for h, n in hi.get("by_harness", {}).items():
                print(f"   - {h}: {n}")
            for c, n in hi.get("by_caller", {}).items():
                print(f"   - caller={c}: {n}")
        else:
            print("🔧 Harness invocations: 0 (no runs in window)")
        print()
        cd = result.get("capability_denied", {})
        if cd.get("total_denied", 0) > 0:
            print(f"🛡️  Capability denied: {cd['total_denied']}")
            for c, n in cd.get("by_cap", {}).items():
                print(f"   - cap={c}: {n}")
        else:
            print("🛡️  Capability denied: 0 (all good)")
        print()
        ia = result.get("inbox_acks", {})
        print(f"📬 INBOX acks: {ia.get('total_acks', 0)}")
        if ia.get("by_actor"):
            for a, n in ia["by_actor"].items():
                print(f"   - by {a}: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
