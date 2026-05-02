#!/usr/bin/env python3
"""Doc Healer — Automatically repairs documentation drift by describing new files.
"""
import sys
import os
import re
from pathlib import Path

try:
    from lib.paths import REPO_ROOT
except ImportError:
    sys.path.append(str(Path(__file__).resolve().parent))
    from lib.paths import REPO_ROOT

def heal_docs():
    import drift_detector
    drifts = drift_detector.detect_drift()
    
    file_drifts = [d for d in drifts if d.startswith("FILE DRIFT")]
    if not file_drifts:
        return "✅ No file drift detected. Documentation is healthy."

    arch_path = REPO_ROOT / ".agent" / "ARCHITECTURE.md"
    if not arch_path.exists():
        return "❌ ARCHITECTURE.md not found."

    content = arch_path.read_text(encoding="utf-8")
    
    for drift in file_drifts:
        # Extract filename: "FILE DRIFT: path/to/file (modified but not in docs)"
        match = re.search(r'FILE DRIFT: ([\w\./_-]+)', drift)
        if not match: continue
        
        file_path = match.group(1)
        full_path = REPO_ROOT / file_path
        if not full_path.exists(): continue
        
        name = full_path.name
        desc = f"System module for {name}."
        
        # Enhanced extraction logic
        try:
            with open(full_path, "r", errors='ignore') as f:
                header = f.read(2000) # Read enough for docstrings
                
                # Python
                py_match = re.search(r'"""(.*?)"""', header, re.DOTALL)
                if py_match:
                    desc = py_match.group(1).strip().split('\n')[0]
                
                # Go / JS (Single line or multi-line comments at start)
                elif header.startswith("//"):
                    desc = header.split('\n')[0].replace("//", "").strip()
                elif header.startswith("/*"):
                    desc = header.split('*/')[0].replace("/*", "").replace("*", "").strip().split('\n')[0]
        except:
            pass

        # Add to ARCHITECTURE.md under a "Recent Additions" section
        if "## 🆕 Recent Additions" not in content:
            content += "\n\n## 🆕 Recent Additions\n\n| File | Description |\n| --- | --- |\n"
        
        entry = f"| `{file_path}` | {desc} |"
        if entry not in content:
            content += entry + "\n"
            print(f"✨ Healed documentation for: {file_path}")

    arch_path.write_text(content, encoding="utf-8")
    return "✅ Documentation healing complete."

if __name__ == "__main__":
    print(heal_docs())
