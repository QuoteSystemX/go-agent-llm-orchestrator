# !/usr/bin/env python3
"""Wiki Sync - The "Live State" maintenance engine for the Archivist.

## Intuition (Mental Model)
The Wiki Sync engine ensures that the repository's documentation is never out of date. 
It acts as a bridge between active development (scripts, ADRs) and the static Wiki, 
automatically updating fragments to reflect the latest state of the codebase.
"""
import os
import json
import re
from pathlib import Path
from datetime import datetime

# Configuration
WIKI_DIR = Path("wiki")
FRAGMENTS_DIR = WIKI_DIR / "fragments"
ADR_DIR = Path("docs/adr")
GOTCHAS_FILE = WIKI_DIR / "GOTCHAS.md"
ARCH_TEMPLATE = WIKI_DIR / "ARCHITECTURE.template.md"
ARCH_FILE = WIKI_DIR / "ARCHITECTURE.md"

def sync_wiki():
    if not WIKI_DIR.exists():
        return {"status": "error", "message": "Wiki directory not found"}

    updates = []
    
    # 1. Sync ADRs to Recent Decisions Fragment
    recent_decisions_fragment = FRAGMENTS_DIR / "core/07-recent-decisions.md"
    if ADR_DIR.exists() and recent_decisions_fragment.exists():
        adrs = list(ADR_DIR.glob("*.md"))
        if adrs:
            with open(recent_decisions_fragment, 'r', encoding='utf-8') as f:
                recent_content = f.read()
            
            new_adrs = []
            for adr in adrs:
                if adr.name not in recent_content:
                    new_adrs.append(adr.name)
            
            if new_adrs:
                with open(recent_decisions_fragment, 'a', encoding='utf-8') as f:
                    for adr_name in new_adrs:
                        f.write(f"- [{adr_name}](../docs/adr/{adr_name})\n")
                updates.append(f"Linked {len(new_adrs)} new ADRs to Recent Decisions fragment")

    # 2. Update Component Map Fragment (Script Inventory)
    component_map_fragment = FRAGMENTS_DIR / "core/04-component-map.md"
    if component_map_fragment.exists():
        scripts_dir = Path(".agent/scripts")
        all_scripts = [f.name for f in scripts_dir.glob("*.py")]
        
        with open(component_map_fragment, 'r', encoding='utf-8') as f:
            comp_content = f.read()
        
        missing_scripts = []
        for script in all_scripts:
            if script not in comp_content:
                missing_scripts.append(script)
        
        if missing_scripts:
            scripts_marker = "├── scripts/"
            if scripts_marker in comp_content:
                new_lines = ""
                for script in sorted(missing_scripts):
                    new_lines += f"│   ├── {script}    (Auto-registered)\n"
                
                updated_comp = comp_content.replace(scripts_marker + "\n", scripts_marker + "\n" + new_lines)
                with open(component_map_fragment, 'w', encoding='utf-8') as f:
                    f.write(updated_comp)
                updates.append(f"Registered {len(missing_scripts)} new scripts in Component Map fragment")

    # 3. Assemble Final ARCHITECTURE.md (Hub Profile)
    import subprocess
    try:
        subprocess.run(["python3", ".agent/scripts/wiki_assembler.py", "--hub"], check=True)
        updates.append("Assembled ARCHITECTURE.md via wiki_assembler")
    except subprocess.CalledProcessError as e:
        updates.append(f"Error during wiki assembly: {e}")

    return {
        "status": "success",
        "updates": updates,
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    result = sync_wiki()
    print(json.dumps(result, indent=2))
