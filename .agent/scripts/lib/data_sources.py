#!/usr/bin/env python3
"""Shared data access helpers for .agent/scripts/.

Narrow by design: one function per data source type, zero business logic.
Each function returns an empty collection on missing/corrupt data — never raises.
Module-level mtime cache prevents redundant I/O within a single process run.
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Bootstrap path (same pattern as all other scripts in this package)
# ---------------------------------------------------------------------------
try:
    from lib.paths import REPO_ROOT
except ImportError:
    SCRIPTS_DIR = Path(__file__).resolve().parents[1]
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    REPO_ROOT = Path(__file__).resolve().parents[3]

from lib.common import load_json_safe

# ---------------------------------------------------------------------------
# Internal cache: {path_str: (mtime, data)}
# ---------------------------------------------------------------------------
_FILE_CACHE: dict = {}


def _cached_load(path: Path) -> dict | list:
    """Load JSON with mtime-based invalidation."""
    key = str(path)
    try:
        mtime = path.stat().st_mtime if path.exists() else 0.0
    except OSError:
        mtime = 0.0

    if key in _FILE_CACHE:
        cached_mtime, cached_data = _FILE_CACHE[key]
        if cached_mtime == mtime:
            return cached_data

    data = load_json_safe(path) if path.exists() else {}
    _FILE_CACHE[key] = (mtime, data)
    return data


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def read_bus_telemetry(
    bus_dir: Optional[Path] = None,
    event_type: Optional[str] = None,
) -> list[dict]:
    """Return all telemetry events from the bus directory.

    Scans `telemetry.json` and any `telemetry-*.json` shards.
    Filters by `event_type` when provided.
    Returns empty list on missing/corrupt files — never raises.

    Token proxy: events may carry `eval_count`, `prompt_eval_count`,
    or `tokens_used`. When none are present, the raw event is still
    returned so callers can derive their own proxy metric.
    """
    if bus_dir is None:
        bus_dir = REPO_ROOT / ".agent" / "bus"

    bus_dir = Path(bus_dir)
    events: list[dict] = []

    candidates = list(bus_dir.glob("telemetry*.json")) if bus_dir.exists() else []

    for path in candidates:
        raw = _cached_load(path)
        # Handle both {"events": [...]} and plain list formats
        if isinstance(raw, dict):
            raw_events = raw.get("events", [])
        elif isinstance(raw, list):
            raw_events = raw
        else:
            raw_events = []

        for ev in raw_events:
            if not isinstance(ev, dict):
                continue
            if event_type is None or ev.get("type") == event_type:
                events.append(ev)

    return events


def read_standards_dir(
    standards_dir: Optional[Path] = None,
    extensions: tuple = (".md", ".json", ".txt"),
) -> list[dict]:
    """Return a list of standard entries from the standards directory.

    Each entry: {"filename": str, "path": Path, "content": str, "first_line": str}
    Returns empty list when directory is absent — never raises.
    """
    if standards_dir is None:
        # Primary: env-configurable global root, fallback to repo-local
        global_root = os.environ.get("AGENT_GLOBAL_ROOT", "")
        if global_root:
            standards_dir = Path(global_root) / "standards"
        else:
            standards_dir = REPO_ROOT / ".agent" / "standards"

    standards_dir = Path(standards_dir)
    if not standards_dir.exists():
        return []

    results = []
    for path in sorted(standards_dir.rglob("*")):
        if path.suffix not in extensions or not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            first_line = next(
                (ln.strip() for ln in content.splitlines() if ln.strip()), ""
            )
            results.append({
                "filename": path.name,
                "path": path,
                "content": content,
                "first_line": first_line,
            })
        except OSError:
            continue

    return results
