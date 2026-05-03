#!/usr/bin/env python3
"""Knowledge Synergy — Cross-project knowledge bridge.
Exports repository-specific decisions to the Global Brain.
"""
import sys
import os
from pathlib import Path

try:
    from lib.paths import REPO_ROOT, GLOBAL_ROOT, GLOBAL_LESSONS_PATH
    from lib.common import load_json_safe
except ImportError:
    sys.path.append(str(Path(__file__).resolve().parent))
    from lib.paths import REPO_ROOT, GLOBAL_ROOT, GLOBAL_LESSONS_PATH
    from lib.common import load_json_safe

def export_adr_to_global(adr_path: Path):
    """Exports a local ADR to the global lessons_learned.md."""
    if not adr_path.exists():
        print(f"❌ ADR not found: {adr_path}")
        return

    content = adr_path.read_text(encoding="utf-8")
    adr_title = adr_path.stem
    
    # Ensure Global Root exists
    GLOBAL_ROOT.mkdir(parents=True, exist_ok=True)
    
    if not GLOBAL_LESSONS_PATH.exists():
        GLOBAL_LESSONS_PATH.write_text("# 🧠 Global Lessons Learned\n\nShared knowledge across all repositories.\n\n", encoding="utf-8")

    global_content = GLOBAL_LESSONS_PATH.read_text(encoding="utf-8")
    
    if adr_title in global_content:
        print(f"⏭️ ADR '{adr_title}' already in Global Brain. Skipping.")
        return

    # Format for global export
    export_block = f"""
## [{adr_title}] (From: {REPO_ROOT.name})
{content}
---
"""
    with open(GLOBAL_LESSONS_PATH, "a", encoding="utf-8") as f:
        f.write(export_block)
    
    print(f"✅ Exported '{adr_title}' to Global Brain at {GLOBAL_LESSONS_PATH}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Knowledge Synergy Tool")
    parser.add_argument("--export", help="Path to local ADR file to export")
    parser.add_argument("--list", action="store_true", help="List global lessons")
    
    args = parser.parse_args()
    
    if args.export:
        export_adr_to_global(Path(args.export))
    elif args.list:
        if GLOBAL_LESSONS_PATH.exists():
            print(GLOBAL_LESSONS_PATH.read_text(encoding="utf-8"))
        else:
            print("Global Brain is empty.")

if __name__ == "__main__":
    main()
