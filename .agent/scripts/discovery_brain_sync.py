#!/usr/bin/env python3
import os
import sys
from pathlib import Path

# Antigravity Standard: Path Resolution
sys.path.append(str(Path(__file__).resolve().parent))
from lib.paths import REPO_ROOT
import semantic_brain_engine as brain

def sync_with_global_brain(intent: str):
    print(f"🧠 Checking Global Brain for intent: '{intent}'...")
    
    # Use the semantic engine we built in Phase 17
    results = brain.search_lessons(intent, top_n=2)
    
    if not results:
        print("ℹ️  No specific matches found in Global Brain. This appears to be a unique requirement.")
        return
        
    print("\n💡 Similar concepts found in other projects:")
    for res in results:
        project = res.get('project', 'Unknown')
        lesson = res.get('summary', 'No summary')
        print(f"  - [{project}]: {lesson}")

def main():
    if len(sys.argv) < 2:
        print("Usage: discovery_brain_sync.py '<intent>'")
        sys.exit(1)
        
    intent = " ".join(sys.argv[1:])
    sync_with_global_brain(intent)

if __name__ == "__main__":
    main()
