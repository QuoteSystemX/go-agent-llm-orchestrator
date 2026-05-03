#!/usr/bin/env python3
"""Context Distiller — Summarize and compress long conversation context.

Reads session state from the Context Bus and generates a compact snapshot
suitable for resuming work in a new conversation window.

Usage:
    python3 distill_context.py                              # auto-distill from bus
    python3 distill_context.py --from-bus                   # explicit bus source
    python3 distill_context.py --summary "Manual summary"   # manual snapshot
    python3 distill_context.py --decisions '["Use pgx", "Switch to Fiber"]'
    python3 distill_context.py --pending '["Write tests", "Deploy"]'
"""
import json
import sys
import argparse
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
BUS_FILE = REPO_ROOT / ".agent" / "bus" / "context.json"
SNAPSHOT_DIR = REPO_ROOT / ".agent" / "bus" / "snapshots"


def _load_bus() -> dict:
    if not BUS_FILE.exists():
        return {"version": "1.0.0", "objects": []}
    try:
        with open(BUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"version": "1.0.0", "objects": []}


def distill_from_bus() -> dict:
    """Analyze bus objects and create a compressed state snapshot."""
    bus = _load_bus()
    objects = bus.get("objects", [])

    if not objects:
        print("📭 Bus is empty. Nothing to distill.")
        return _create_snapshot("No data on bus.", [], [], {})

    # Extract decisions from verification_result objects
    decisions = []
    pending = []
    file_impact = {}
    agents_seen = set()

    for obj in objects:
        agents_seen.add(obj.get("author", "unknown"))
        obj_type = obj.get("type", "")
        content = obj.get("content", {})

        if obj_type == "verification_result":
            status = content.get("status", "")
            summary = content.get("summary", "")
            if summary:
                decisions.append(f"[{status}] {summary}")

        elif obj_type == "requirement":
            tasks = content.get("tasks", [])
            for t in tasks:
                pending.append(f"{t.get('agent', '?')}: {t.get('instruction', '?')[:80]}")

        elif obj_type == "state_snapshot":
            # Merge existing snapshot data
            decisions.extend(content.get("decisions", []))
            pending.extend(content.get("pending_tasks", []))
            file_impact.update(content.get("file_impact_map", {}))

        elif obj_type == "code_chunk":
            files = content.get("files", [])
            for f in files:
                file_impact[f] = obj.get("author", "unknown")

        elif obj_type == "memory_note":
            note = content.get("note", content.get("text", ""))
            if note:
                decisions.append(f"[NOTE] {note[:200]}")

    summary = (
        f"Distilled from {len(objects)} bus objects. "
        f"Agents: {', '.join(sorted(agents_seen))}. "
        f"Decisions: {len(decisions)}, Pending: {len(pending)}."
    )

    return _create_snapshot(summary, decisions, pending, file_impact)


def _create_snapshot(summary: str, decisions: list, pending: list,
                     file_impact: dict) -> dict:
    """Create a structured state snapshot."""
    snapshot_id = f"distill_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    snapshot = {
        "id": snapshot_id,
        "type": "state_snapshot",
        "author": "distill_context",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "content": {
            "summary": summary,
            "decisions": decisions[:50],  # Cap at 50
            "pending_tasks": pending[:30],  # Cap at 30
            "file_impact_map": dict(list(file_impact.items())[:100]),  # Cap at 100
        },
    }
    return snapshot


def save_snapshot(snapshot: dict) -> Path:
    """Save snapshot to both bus and snapshots archive."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    # Save to archive
    filename = f"{snapshot['id']}.json"
    archive_path = SNAPSHOT_DIR / filename
    with open(archive_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)

    # Push to bus
    bus = _load_bus()
    bus.setdefault("objects", []).append(snapshot)

    tmp = BUS_FILE.with_suffix(".tmp")
    BUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(bus, f, indent=2, ensure_ascii=False)
    tmp.replace(BUS_FILE)

    return archive_path


def main():
    parser = argparse.ArgumentParser(description="Context Distiller")
    parser.add_argument("--from-bus", action="store_true", default=True,
                        help="Distill from Context Bus (default)")
    parser.add_argument("--summary", help="Manual summary text")
    parser.add_argument("--decisions", help="JSON array of decision strings")
    parser.add_argument("--pending", help="JSON array of pending task strings")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print snapshot without saving")

    args = parser.parse_args()

    # Manual mode
    if args.summary:
        decisions = json.loads(args.decisions) if args.decisions else []
        pending = json.loads(args.pending) if args.pending else []
        snapshot = _create_snapshot(args.summary, decisions, pending, {})
    else:
        snapshot = distill_from_bus()

    if args.dry_run:
        print(json.dumps(snapshot, indent=2, ensure_ascii=False))
        return

    archive_path = save_snapshot(snapshot)
    sid = snapshot["id"]
    print(f"✅ Context distilled → {sid}")
    print(f"   Archive: {archive_path.relative_to(REPO_ROOT)}")
    print(f"   Bus: pushed to context.json")
    print(f"\n💡 To resume in a new conversation:")
    print(f'   "Resume from distill snapshot {sid}"')
    print(f"   Then run: python3 .agent/scripts/bus_manager.py pull --id {sid}")


if __name__ == "__main__":
    main()
