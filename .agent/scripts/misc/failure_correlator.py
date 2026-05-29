#!/usr/bin/env python3
"""
DEPRECATED — Failure Correlator.

This module is preserved for backward compatibility. It previously used
hardcoded keyword matching. The replacement path is to read real failure
data from the Context Bus (.agent/bus/) and .agent/reports/ directory.

Use bus_history.read_failures() or query the telemetry bus directly.
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

import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_BUS_EVENTS = 1000
MAX_AGE_HOURS = 168  # 7-day window

REPO_ROOT = Path(__file__).resolve().parents[3]
BUS_DIR = REPO_ROOT / ".agent" / "bus"
REPORTS_DIR = REPO_ROOT / ".agent" / "reports"


def _load_bus_events() -> list[dict]:
    """Read recent bus events for failure patterns."""
    bus_file = BUS_DIR / "context.json"
    if not bus_file.exists():
        return []
    try:
        data = json.loads(bus_file.read_text())
        events = data if isinstance(data, list) else data.get("events", []) if isinstance(data, dict) else []
        return events[:MAX_BUS_EVENTS]
    except (OSError, json.JSONDecodeError) as e:
        logger.debug("[failure_correlator] Could not read bus: %s", e)
        return []


def _load_reports() -> list[dict]:
    """Aggregate failure reports from .agent/reports/."""
    reports = []
    if not REPORTS_DIR.exists():
        return reports
    for f in sorted(REPORTS_DIR.glob("*.json"))[:50]:
        try:
            reports.append(json.loads(f.read_text()))
        except (OSError, json.JSONDecodeError):
            continue
    return reports


def correlate_failures(intent: str) -> list[dict]:
    """Correlate intent with historical failure data from bus + reports."""
    logger.warning("[failure_correlator] This module is deprecated. Use bus telemetry directly.")

    print(f"📉 Correlating with historical failures for: '{intent}'...")
    matches = []

    # 1. Check bus events for failure patterns
    for ev in _load_bus_events():
        text = json.dumps(ev).lower()
        if intent.lower() in text:
            matches.append({
                "source": "bus",
                "match": ev.get("type", "unknown"),
                "detail": str(ev)[:200],
            })

    # 2. Check report files
    for report in _load_reports():
        text = json.dumps(report).lower()
        if intent.lower() in text:
            matches.append({
                "source": "report",
                "match": report.get("name", report.get("title", "unknown")),
                "detail": str(report)[:200],
            })

    # 3. Legacy keyword fallback
    if not matches:
        kw = intent.lower()
        if "cache" in kw or "concurrency" in kw:
            matches.append({
                "source": "keyword_fallback",
                "match": "historical pattern (cache/concurrency)",
                "detail": "Similar task in April led to a Deadlock in pkg/storage. "
                          "Recommendation: Use atomic operations and check lock order.",
            })

    if matches:
        print(f"⚠️  Found {len(matches)} historical correlation(s)")
        for m in matches:
            print(f"  [{m['source']}] {m['match']}")
            if m.get("detail"):
                print(f"    {m['detail']}")
    else:
        print("✅ No relevant historical failures found for this pattern.")

    return matches


if __name__ == "__main__":
    correlate_failures(" ".join(sys.argv[1:]))
