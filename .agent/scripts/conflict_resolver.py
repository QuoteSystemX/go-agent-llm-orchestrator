#!/usr/bin/env python3
"""Conflict Resolver — Detects ID collisions and state conflicts on the bus.
"""
import sys
import json
from pathlib import Path
from collections import defaultdict

try:
    from lib.paths import BUS_DIR
    from lib.common import load_json_safe, save_json_atomic
except ImportError:
    sys.path.append(str(Path(__file__).resolve().parent))
    from lib.paths import BUS_DIR
    from lib.common import load_json_safe, save_json_atomic

def resolve_conflicts():
    bus_file = BUS_DIR / "context.json"
    if not bus_file.exists():
        return "No bus data found."

    data = load_json_safe(bus_file)
    objects = data.get("objects", [])
    
    ids = defaultdict(list)
    for obj in objects:
        ids[obj.get("id")].append(obj)

    conflicts = []
    for obj_id, objs in ids.items():
        if len(objs) > 1:
            # Check if they are actually different
            contents = [json.dumps(o.get("content"), sort_keys=True) for o in objs]
            if len(set(contents)) > 1:
                conflicts.append({
                    "id": obj_id,
                    "count": len(objs),
                    "authors": list(set(o.get("author") for o in objs))
                })

    if not conflicts:
        return "✅ No conflicts detected on the bus."

    report = ["⚠️  BUS CONFLICTS DETECTED:"]
    for c in conflicts:
        report.append(f"  - ID: '{c['id']}' has {c['count']} conflicting versions from {c['authors']}")
        
    return "\n".join(report)

if __name__ == "__main__":
    print(resolve_conflicts())
