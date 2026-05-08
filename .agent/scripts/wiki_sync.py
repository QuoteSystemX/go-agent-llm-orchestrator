# !/usr/bin/env python3
"""Wiki Sync - The "Live State" maintenance engine for the Archivist.

## Intuition (Mental Model)
The Wiki Sync engine ensures that the repository's documentation is never out of date. 
It acts as a bridge between active development (scripts, ADRs) and the static Wiki, 
automatically updating fragments to reflect the latest state of the codebase.
"""
import json
import subprocess
from pathlib import Path
from datetime import datetime

WIKI_DIR = Path("wiki")
FRAGMENTS_DIR = WIKI_DIR / "fragments"
ADR_DIR = Path("docs/adr")
DECISIONS_FRAGMENT = FRAGMENTS_DIR / "core/07-recent-decisions.md"
COMPONENTS_FRAGMENT = FRAGMENTS_DIR / "core/04-component-map.md"

def sync_adrs() -> str:
    if not (ADR_DIR.exists() and DECISIONS_FRAGMENT.exists()):
        return ""
        
    adrs = list(ADR_DIR.glob("*.md"))
    current_content = DECISIONS_FRAGMENT.read_text()
    new_links = [f"- [{a.name}](../docs/adr/{a.name})" for a in adrs if a.name not in current_content]
    
    if not new_links:
        return ""
        
    DECISIONS_FRAGMENT.write_text(current_content + "\n".join(new_links) + "\n")
    return f"Linked {len(new_links)} new ADRs"

def sync_scripts() -> str:
    if not COMPONENTS_FRAGMENT.exists():
        return ""
        
    scripts = [f.name for f in Path(".agent/scripts").glob("*.py")]
    content = COMPONENTS_FRAGMENT.read_text()
    missing = [s for s in scripts if s not in content]
    
    if not missing:
        return ""
        
    marker = "├── scripts/\n"
    if marker not in content:
        return "Warning: Scripts marker missing in fragment"
        
    new_entries = "".join(f"│   ├── {s}    (Auto-registered)\n" for s in sorted(missing))
    COMPONENTS_FRAGMENT.write_text(content.replace(marker, marker + new_entries))
    return f"Registered {len(missing)} new scripts"

def run_assembly():
    try:
        subprocess.run(["python3", ".agent/scripts/wiki_assembler.py", "--hub"], check=True)
        return "Assembled ARCHITECTURE.md"
    except subprocess.CalledProcessError as e:
        return f"Assembly failed: {e}"

def sync_wiki():
    if not WIKI_DIR.exists():
        return {"status": "error", "message": "Wiki missing"}

    results = [sync_adrs(), sync_scripts(), run_assembly()]
    return {
        "status": "success", 
        "updates": [r for r in results if r],
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    print(json.dumps(sync_wiki(), indent=2))
