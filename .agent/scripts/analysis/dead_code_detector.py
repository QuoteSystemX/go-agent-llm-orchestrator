#!/usr/bin/env python3
"""Dead Code Detector — Finds unreferenced scripts in the workspace.
"""

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    import sys
    from pathlib import Path
    SCRIPTS_DIR = Path(__file__).resolve().parents[1]
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.append(str(SCRIPTS_DIR))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev"]:
        d_path = str(SCRIPTS_DIR / domain)
        if d_path not in sys.path:
            sys.path.append(d_path)

import os
import subprocess
from pathlib import Path

def find_unused_scripts():
    print("🕵️  Searching for dead script modules...")
    
    scripts_dir = Path(".agent/scripts")
    skills_dir = Path(".agent/skills")
    
    EXCLUDE_DIRS = {"tests", "__pycache__"}

    all_scripts = list(scripts_dir.rglob("*.py")) + list(skills_dir.rglob("*.py"))
    all_scripts = [
        s for s in all_scripts
        if s.name != "__init__.py" and not EXCLUDE_DIRS.intersection(s.parts)
    ]
    
    search_dirs = [
        ".agent/workflows", 
        ".github/workflows", 
        ".agent/scripts", 
        ".agent/skills", 
        ".agent/knowledge",
        ".agent/agents",
        ".agent/rules",
        "CODEBASE.md",
        "ARCHITECTURE.md"
    ]
    
    EXCLUDE_LIST = [
        "dead_code_detector.py", # Self
        "paths.py",             # Core lib
        "common.py",            # Core lib
        "output_bridge.py",      # Binary bridge
        "bus_debugger.py"       # Debug utility
    ]
    
    unused = []
    for script in all_scripts:
        name = script.name
        if name in EXCLUDE_LIST: continue
        
        # Grep for the filename in all relevant directories
        found = False
        for sdir in search_dirs:
            if not Path(sdir).exists(): continue
            try:
                # Use grep -r to find references
                res = subprocess.run(["grep", "-r", name, sdir], capture_output=True, text=True)
                for line in res.stdout.splitlines():
                    if not line.strip(): continue
                    # Extract the file path where grep found the match
                    match_file = line.split(":")[0]
                    # If match is in a DIFFERENT file, it's a reference!
                    if Path(match_file).resolve() != script.resolve():
                        found = True
                        break
                if found: break
            except:
                continue
        
        if not found:
            unused.append(script)
            
    return unused

import json

def main():
    unused = find_unused_scripts()
    
    report = {
        "unused_count": len(unused),
        "unused_scripts": [str(s) for s in unused],
        "status": "PASS" if not unused else "WARN"
    }
    
    bus_file = Path(".agent/bus/dead_code_metrics.json")
    bus_file.parent.mkdir(parents=True, exist_ok=True)
    bus_file.write_text(json.dumps(report, indent=2))

    if unused:
        print(f"🛑 FOUND {len(unused)} UNUSED SCRIPTS:")
        for s in unused:
            print(f"  - {s}")
    else:
        print("✅ No dead scripts found. Repository is lean.")

if __name__ == "__main__":
    main()
