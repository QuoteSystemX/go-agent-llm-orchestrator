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
    "telemetry",
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

    data = load_json_safe(BUS_FILE)
    if not data:
        data = {"version": "1.0.0", "objects": []}

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

def wait_for_object(obj_id: str, timeout: int = 30) -> None:
    """Wait for an object with a specific ID to appear on the bus."""
    import time
    print(f"⏳ Waiting for object '{obj_id}' on the bus (timeout: {timeout}s)...")
    start = time.time()
    while time.time() - start < timeout:
        data = load_json_safe(BUS_FILE)
        objects = data.get("objects", [])
        for obj in objects:
            if obj["id"] == obj_id:
                print(f"✅ Found object '{obj_id}' after {int(time.time() - start)}s.")
                print(json.dumps(obj, indent=2, ensure_ascii=False))
                return
        time.sleep(2)
    print(f"❌ Timeout: Object '{obj_id}' not found after {timeout}s.")
    sys.exit(1)

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

    # wait
    wait_p = sub.add_parser("wait", help="Wait for an object by ID")
    wait_p.add_argument("--id", required=True)
    wait_p.add_argument("--timeout", type=int, default=30)

    args = parser.parse_args()
    if args.command == "push":
        push(args.id, args.type, args.author, args.content, args.metadata)
    elif args.command == "wait":
        wait_for_object(args.id, args.timeout)
    else:
        print("Command not implemented.")
        sys.exit(1)

if __name__ == "__main__":
    main()
