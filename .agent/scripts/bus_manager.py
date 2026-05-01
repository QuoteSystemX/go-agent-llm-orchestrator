#!/usr/bin/env python3
"""Context Bus Manager — Push, pull, list, and peek objects on the shared bus.

The Context Bus is a file-based structured data exchange layer between agents.
All bus objects are stored in .agent/bus/context.json and validated against
.agent/bus/schema.json.

Usage:
    python3 bus_manager.py push --id req_001 --type requirement --author orchestrator --content '{"spec": "..."}'
    python3 bus_manager.py pull --id req_001
    python3 bus_manager.py list
    python3 bus_manager.py peek [--limit 5]
    python3 bus_manager.py delete --id req_001
    python3 bus_manager.py clear
"""
import json
import sys
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).parent.parent.parent
BUS_FILE = REPO_ROOT / ".agent" / "bus" / "context.json"

VALID_TYPES = [
    "requirement", "api_spec", "code_chunk",
    "verification_result", "memory_note", "state_snapshot",
]


def _load_bus() -> dict:
    """Load the bus file, creating it if it doesn't exist."""
    if not BUS_FILE.exists():
        return {"version": "1.0.0", "objects": []}
    try:
        with open(BUS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "objects" not in data:
            data["objects"] = []
        return data
    except (json.JSONDecodeError, OSError):
        return {"version": "1.0.0", "objects": []}


def _save_bus(data: dict) -> None:
    """Save the bus file atomically."""
    BUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = BUS_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp.replace(BUS_FILE)


def push(obj_id: str, obj_type: str, author: str, content_str: str,
         metadata: Optional[str] = None) -> None:
    """Push a new object onto the bus."""
    if obj_type not in VALID_TYPES:
        print(f"❌ Invalid type '{obj_type}'. Must be one of: {', '.join(VALID_TYPES)}")
        sys.exit(1)

    try:
        content = json.loads(content_str)
    except json.JSONDecodeError:
        # Treat as plain text
        content = {"text": content_str}

    meta = {}
    if metadata:
        try:
            meta = json.loads(metadata)
        except json.JSONDecodeError:
            meta = {"raw": metadata}

    bus = _load_bus()

    # Check for duplicate ID
    existing_ids = {obj["id"] for obj in bus["objects"]}
    if obj_id in existing_ids:
        print(f"⚠️  Object '{obj_id}' already exists. Use delete first or choose a new ID.")
        sys.exit(1)

    new_obj = {
        "id": obj_id,
        "type": obj_type,
        "author": author,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "content": content,
    }
    if meta:
        new_obj["metadata"] = meta

    bus["objects"].append(new_obj)
    _save_bus(bus)
    print(f"✅ Pushed '{obj_id}' ({obj_type}) by {author}. Bus now has {len(bus['objects'])} object(s).")


def pull(obj_id: str) -> None:
    """Pull (retrieve and print) an object by ID."""
    bus = _load_bus()

    for obj in bus["objects"]:
        if obj["id"] == obj_id:
            print(json.dumps(obj, indent=2, ensure_ascii=False))
            return

    print(f"❌ Object '{obj_id}' not found on the bus.")
    sys.exit(1)


def list_objects() -> None:
    """List all objects on the bus (summary view)."""
    bus = _load_bus()

    if not bus["objects"]:
        print("📭 Bus is empty.")
        return

    print(f"📬 Context Bus — {len(bus['objects'])} object(s):\n")
    print(f"{'ID':<25} {'Type':<22} {'Author':<20} {'Timestamp'}")
    print("-" * 90)
    for obj in bus["objects"]:
        ts = obj.get("timestamp", "?")[:19]
        print(f"{obj['id']:<25} {obj['type']:<22} {obj['author']:<20} {ts}")


def peek(limit: int = 5) -> None:
    """Show the most recent objects (full content)."""
    bus = _load_bus()

    if not bus["objects"]:
        print("📭 Bus is empty.")
        return

    recent = bus["objects"][-limit:]
    print(f"📬 Last {len(recent)} object(s):\n")
    for obj in recent:
        print(json.dumps(obj, indent=2, ensure_ascii=False))
        print()


def delete(obj_id: str) -> None:
    """Delete an object by ID."""
    bus = _load_bus()
    original_count = len(bus["objects"])
    bus["objects"] = [o for o in bus["objects"] if o["id"] != obj_id]

    if len(bus["objects"]) == original_count:
        print(f"❌ Object '{obj_id}' not found.")
        sys.exit(1)

    _save_bus(bus)
    print(f"🗑️  Deleted '{obj_id}'. Bus now has {len(bus['objects'])} object(s).")


def clear() -> None:
    """Clear all objects from the bus."""
    bus = _load_bus()
    count = len(bus["objects"])
    bus["objects"] = []
    _save_bus(bus)
    print(f"🗑️  Cleared {count} object(s) from the bus.")


def main():
    parser = argparse.ArgumentParser(description="Context Bus Manager")
    sub = parser.add_subparsers(dest="command", help="Command")

    # push
    push_p = sub.add_parser("push", help="Push an object to the bus")
    push_p.add_argument("--id", required=True, help="Unique object ID")
    push_p.add_argument("--type", required=True, choices=VALID_TYPES, help="Object type")
    push_p.add_argument("--author", required=True, help="Agent that created the object")
    push_p.add_argument("--content", required=True, help="JSON content string or plain text")
    push_p.add_argument("--metadata", help="Optional JSON metadata")

    # pull
    pull_p = sub.add_parser("pull", help="Pull an object by ID")
    pull_p.add_argument("--id", required=True, help="Object ID to retrieve")

    # list
    sub.add_parser("list", help="List all objects (summary)")

    # peek
    peek_p = sub.add_parser("peek", help="Show recent objects (full)")
    peek_p.add_argument("--limit", type=int, default=5, help="Number of recent objects")

    # delete
    del_p = sub.add_parser("delete", help="Delete an object by ID")
    del_p.add_argument("--id", required=True, help="Object ID to delete")

    # clear
    sub.add_parser("clear", help="Clear all objects from the bus")

    args = parser.parse_args()

    if args.command == "push":
        push(args.id, args.type, args.author, args.content, args.metadata)
    elif args.command == "pull":
        pull(args.id)
    elif args.command == "list":
        list_objects()
    elif args.command == "peek":
        peek(args.limit)
    elif args.command == "delete":
        delete(args.id)
    elif args.command == "clear":
        clear()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
