#!/usr/bin/env python3
import sys
import subprocess
from pathlib import Path

def analyze_impact(intent: str):
    print(f"🕸️  Calculating Blast Radius for: '{intent}'...")
    
    # 1. Identify potential targets in intent
    keywords = [w for w in intent.split() if len(w) > 4]
    impacted_files = set()
    
    for kw in keywords:
        try:
            # Find files where this keyword is used (simulating dependency tracking)
            grep_out = subprocess.check_output(['grep', '-rl', kw, '.'], cwd=Path.cwd()).decode().splitlines()
            impacted_files.update([f for f in grep_out if not f.startswith('./.git') and not f.startswith('./.agent')])
        except:
            pass
            
    print(f"📊 Impact Analysis: {len(impacted_files)} files potentially affected.")
    for f in list(impacted_files)[:5]:
        print(f"  - {f}")
    if len(impacted_files) > 5:
        print(f"  ... and {len(impacted_files) - 5} more.")

if __name__ == "__main__":
    analyze_impact(" ".join(sys.argv[1:]))
