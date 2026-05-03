#!/usr/bin/env python3
import os
import sys
import subprocess
import re
from pathlib import Path

# Antigravity Standard: Path Resolution
sys.path.append(str(Path(__file__).resolve().parent))
from lib.paths import REPO_ROOT

def search_codebase(intent: str):
    print(f"🔍 Autonomously investigating context for: '{intent}'...")
    
    # Extract potential keywords
    keywords = re.findall(r'\b\w{4,}\b', intent)
    results = {}
    
    for kw in keywords:
        # Search for files with these names
        try:
            find_out = subprocess.check_output(['find', '.', '-name', f'*{kw}*'], cwd=REPO_ROOT).decode()
            if find_out:
                results[kw] = find_out.splitlines()[:3] # Top 3 matches
        except:
            pass
            
    return results

def main():
    if len(sys.argv) < 2:
        sys.exit(1)
        
    intent = " ".join(sys.argv[1:])
    # Using simple regex instead of re import for now to keep it lean
    import re
    
    context = search_codebase(intent)
    
    if not context:
        print("ℹ️  No immediate code matches found. Proceeding with standard discovery.")
        return

    print("\n💡 I've proactively found these relevant files/structures:")
    for kw, files in context.items():
        print(f"  - Relevant to '{kw}':")
        for f in files:
            print(f"    - {f}")
    
    print("\n[CONTEXT AUTOFILL COMPLETE — Analyst will use this data to refine the interview]")

if __name__ == "__main__":
    main()
