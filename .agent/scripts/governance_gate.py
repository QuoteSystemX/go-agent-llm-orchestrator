#!/usr/bin/env python3
"""Governance Gate (The Sentinel).

Enforces the 'Proactive Documentation' rule: new files must be defined in the
Wiki (Stories or ADRs) before implementation.
"""
import sys
import os
import re
import json
from pathlib import Path

WIKI_STORIES = Path("wiki/stories")
WIKI_ADR = Path("wiki/decisions")

def is_file_in_wiki(file_path):
    # Check all stories and ADRs for the file path
    for wiki_dir in [WIKI_STORIES, WIKI_ADR]:
        if not wiki_dir.exists(): continue
        for path in wiki_dir.rglob("*.md"):
            with open(path, "r", errors="ignore") as f:
                content = f.read()
                if file_path in content or os.path.basename(file_path) in content:
                    return True
    return False

def check_governance(impacted_files):
    print("🛡️ Checking Governance Gate (Wiki-First Compliance)...")
    
    violations = []
    for f in impacted_files:
        # Check if file exists (it's new if it doesn't exist yet or is empty)
        # In this context, we check if the file is being created.
        if not os.path.exists(f) or os.path.getsize(f) == 0:
            if not is_file_in_wiki(f):
                violations.append(f)
                
    if violations:
        print(f"❌ GOVERNANCE VETO: New files detected without Wiki definition:")
        for v in violations:
            print(f"   - {v}")
        print("\n👉 Please create a Story Card or ADR in 'wiki/' first.")
        return False
        
    print("✅ Governance check passed.")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 governance_gate.py <impacted_files_json>")
        sys.exit(1)
        
    impacted_files = json.loads(sys.argv[1])
    success = check_governance(impacted_files)
    sys.exit(0 if success else 1)
