#!/usr/bin/env python3
"""Bus Debugger — Interactive tool for inspecting the Context Bus.
"""
import sys
import json
from pathlib import Path

try:
    from lib.paths import BUS_DIR
    from lib.common import load_json_safe
except ImportError:
    sys.path.append(str(Path(__file__).resolve().parent))
    from lib.paths import BUS_DIR
    from lib.common import load_json_safe

BUS_FILE = BUS_DIR / "context.json"

def interactive_debug():
    """Simple interactive loop to peek at bus objects."""
    print("🕵️  ANTIGRAVITY BUS DEBUGGER")
    print("Commands: [l]ist, [p]eek <id>, [q]uit")
    
    while True:
        try:
            cmd = input("\n> ").strip().split()
            if not cmd: continue
            
            action = cmd[0].lower()
            
            data = load_json_safe(BUS_FILE)
            objects = data.get("objects", [])

            if action == 'l':
                print(f"Total objects: {len(objects)}")
                for obj in objects:
                    print(f"  [{obj['id']}] {obj['type']} by {obj['author']}")
            
            elif action == 'p' and len(cmd) > 1:
                obj_id = cmd[1]
                found = next((o for o in objects if o['id'] == obj_id), None)
                if found:
                    print(json.dumps(found, indent=2, ensure_ascii=False))
                else:
                    print(f"Object '{obj_id}' not found.")
            
            elif action == 'q':
                break
            else:
                print("Unknown command.")
        except EOFError:
            break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    interactive_debug()
