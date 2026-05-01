#!/usr/bin/env python3
"""Rollback Task — Reverts code changes and cleans up associated bus objects.
"""
import sys
import subprocess
from pathlib import Path

try:
    from lib.paths import REPO_ROOT, BUS_DIR
    from lib.common import load_json_safe, save_json_atomic
except ImportError:
    sys.path.append(str(Path(__file__).resolve().parent))
    from lib.paths import REPO_ROOT, BUS_DIR
    from lib.common import load_json_safe, save_json_atomic

def rollback_git():
    print("🔄 Reverting code changes (git reset --hard)...")
    try:
        subprocess.check_call(["git", "reset", "--hard", "HEAD"], cwd=REPO_ROOT)
        subprocess.check_call(["git", "clean", "-fd"], cwd=REPO_ROOT)
        return True
    except Exception as e:
        print(f"❌ Git rollback failed: {e}")
        return False

def clean_bus(author_filter: str = None):
    print(f"🧹 Cleaning bus objects{' for author ' + author_filter if author_filter else ''}...")
    bus_file = BUS_DIR / "context.json"
    if not bus_file.exists():
        return

    data = load_json_safe(bus_file)
    objects = data.get("objects", [])
    
    initial_count = len(objects)
    if author_filter:
        new_objects = [obj for obj in objects if obj.get("author") != author_filter]
    else:
        # Remove last 5 objects if no filter
        new_objects = objects[:-5] if len(objects) > 5 else []

    data["objects"] = new_objects
    save_json_atomic(bus_file, data)
    print(f"✅ Removed {initial_count - len(new_objects)} objects from bus.")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Rollback Task and State")
    parser.add_argument("--author", help="Filter bus cleanup by author name")
    args = parser.parse_args()

    if rollback_git():
        clean_bus(args.author)
        print("\n✨ Rollback complete. Workspace is clean.")

if __name__ == "__main__":
    main()
