#!/usr/bin/env python3
"""Context Bus Manager — Push, pull, list, and peek objects on the shared bus.
"""
import json
import sys
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Import from common lib
try:
    from lib.paths import BUS_DIR, WATCHDOG_RULES_PATH
    from lib.common import load_json_safe, save_json_atomic
except ImportError:
    sys.path.append(str(Path(__file__).resolve().parent))
    from lib.paths import BUS_DIR, WATCHDOG_RULES_PATH
    from lib.common import load_json_safe, save_json_atomic

BUS_FILE = BUS_DIR / "context.json"

VALID_TYPES = [
    "requirement", "api_spec", "code_chunk",
    "verification_result", "memory_note", "state_snapshot",
    "telemetry", "proposed_fix", "incident",
]

def _check_telemetry_limits(content: dict):
    """Check if telemetry exceeds watchdog limits and alert."""
    rules = load_json_safe(WATCHDOG_RULES_PATH)
    if not rules:
        return

    limits = rules.get("limits", {})
    tokens = content.get("total_tokens", 0)
    cost = content.get("total_cost_usd", 0)

    if tokens > limits.get("token_budget_per_task", 100000):
        print(f"\n⚠️  BUS ALERT: Telemetry indicates budget breach! Tokens: {tokens}")
    if cost > limits.get("cost_limit_per_task_usd", 2.0):
        print(f"\n⚠️  BUS ALERT: Telemetry indicates budget breach! Cost: ${cost:.2f}")

def push(obj_id: str, obj_type: str, author: str, content_str: str,
         metadata: Optional[str] = None) -> None:
    """Push a new object onto the bus."""
    if obj_type not in VALID_TYPES:
        print(f"❌ Invalid type '{obj_type}'. Must be one of: {', '.join(VALID_TYPES)}")
        sys.exit(1)

    data = load_json_safe(BUS_FILE) or {"version": "1.0.0", "objects": []}
    
    # Check for duplicates
    if any(obj["id"] == obj_id for obj in data.get("objects", [])):
        print(f"❌ Error: Object with ID '{obj_id}' already exists on the bus.")
        sys.exit(1)

    try:
        content = json.loads(content_str)
    except json.JSONDecodeError:
        content = {"text": content_str}

    # Alert on telemetry push
    if obj_type == "telemetry":
        _check_telemetry_limits(content)

    meta = {}
    if metadata:
        try:
            meta = json.loads(metadata)
        except json.JSONDecodeError:
            meta = {"raw": metadata}

    new_obj = {
        "id": obj_id,
        "type": obj_type,
        "author": author,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "content": content,
    }
    if meta:
        new_obj["metadata"] = meta

    data["objects"].append(new_obj)
    save_json_atomic(BUS_FILE, data)
    print(f"✅ Pushed '{obj_id}' ({obj_type}) by {author}.")

def pull(obj_id: str) -> None:
    """Pull an object from the bus and print as JSON."""
    data = load_json_safe(BUS_FILE)
    if not data:
        print(f"❌ Bus is empty.")
        sys.exit(1)
    
    for obj in data.get("objects", []):
        if obj["id"] == obj_id:
            print(json.dumps(obj))
            return
            
    print(f"❌ Object '{obj_id}' not found.")
    sys.exit(1)

def delete(obj_id: str) -> None:
    """Remove an object from the bus by ID."""
    data = load_json_safe(BUS_FILE)
    if not data: return
    
    original_count = len(data.get("objects", []))
    data["objects"] = [obj for obj in data.get("objects", []) if obj["id"] != obj_id]
    
    if len(data["objects"]) < original_count:
        save_json_atomic(BUS_FILE, data)
        print(f"✅ Deleted object '{obj_id}'.")
    else:
        print(f"ℹ️ Object '{obj_id}' not found.")

def clear() -> None:
    """Empty the context bus."""
    data = {"version": "1.0.0", "objects": []}
    save_json_atomic(BUS_FILE, data)
    print("🧹 Context bus cleared.")

def list_objects() -> None:
    """List all objects on the bus."""
    data = load_json_safe(BUS_FILE)
    objects = data.get("objects", []) if data else []
    
    if not objects:
        print("ℹ️ Bus is empty.")
        return
        
    print(f"🚌 Context Bus ({len(objects)} objects):")
    for obj in objects:
        print(f"- [{obj['timestamp']}] {obj['id']} ({obj['type']}) by {obj['author']}")

def wait_for_object(obj_id: str, timeout: int = 30) -> Optional[dict]:
    """Wait for an object with a specific ID to appear on the bus and return it."""
    import time
    print(f"⏳ Waiting for object '{obj_id}' on the bus (timeout: {timeout}s)...")
    start = time.time()
    while time.time() - start < timeout:
        data = load_json_safe(BUS_FILE)
        objects = data.get("objects", []) if data else []
        for obj in objects:
            if obj["id"] == obj_id:
                print(f"✅ Found object '{obj_id}' after {int(time.time() - start)}s.")
                return obj
        time.sleep(1)
    print(f"❌ Timeout: Object '{obj_id}' not found after {timeout}s.")
    return None

def main():
    parser = argparse.ArgumentParser(description="Context Bus Manager")
    sub = parser.add_subparsers(dest="command", help="Command")

    # push
    push_p = sub.add_parser("push", help="Push an object to the bus")
    push_p.add_argument("--id", required=True)
    push_p.add_argument("--type", required=True, choices=VALID_TYPES)
    push_p.add_argument("--author", required=True)
    push_p.add_argument("--content", required=True)
    push_p.add_argument("--metadata", help="Optional JSON metadata")

    # pull
    pull_p = sub.add_parser("pull", help="Pull an object by ID")
    pull_p.add_argument("--id", required=True)

    # delete
    del_p = sub.add_parser("delete", help="Delete an object by ID")
    del_p.add_argument("--id", required=True)

    # list
    sub.add_parser("list", help="List all objects")

    # clear
    sub.add_parser("clear", help="Clear the bus")

    # wait
    wait_p = sub.add_parser("wait", help="Wait for an object by ID")
    wait_p.add_argument("--id", required=True)
    wait_p.add_argument("--timeout", type=int, default=30)

    args = parser.parse_args()
    if args.command == "push":
        push(args.id, args.type, args.author, args.content, args.metadata)
    elif args.command == "pull":
        pull(args.id)
    elif args.command == "delete":
        delete(args.id)
    elif args.command == "list":
        list_objects()
    elif args.command == "clear":
        clear()
    elif args.command == "wait":
        wait_for_object(args.id, args.timeout)
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
