#!/usr/bin/env python3
"""Wiki Sync - The "Live State" maintenance engine for the Archivist.
Consolidates ADRs, experiences, and code changes into the evergreen Wiki.
"""
import os
import json
import re
from pathlib import Path
from datetime import datetime

# Configuration
WIKI_DIR = Path("wiki")
ADR_DIR = Path("docs/adr")
GOTCHAS_FILE = WIKI_DIR / "GOTCHAS.md"
ARCH_FILE = WIKI_DIR / "ARCHITECTURE.md"

def sync_wiki():
    if not WIKI_DIR.exists():
        return {"status": "error", "message": "Wiki directory not found"}

    updates = []
    
    # 1. Sync ADRs to Architecture Wiki
    if ADR_DIR.exists():
        adrs = list(ADR_DIR.glob("*.md"))
        if adrs:
            # Simple heuristic: ensure ARCHITECTURE.md mentions latest ADRs
            with open(ARCH_FILE, 'r', encoding='utf-8') as f:
                arch_content = f.read()
            
            new_adrs = []
            for adr in adrs:
                if adr.name not in arch_content:
                    new_adrs.append(adr.name)
            
            if new_adrs:
                # Add ADR references to ARCHITECTURE.md (append to bottom for now)
                with open(ARCH_FILE, 'a', encoding='utf-8') as f:
                    f.write(f"\n\n## 📋 Recent Decisions (Synced by Archivist)\n")
                    for adr_name in new_adrs:
                        f.write(f"- [{adr_name}](../docs/adr/{adr_name})\n")
                updates.append(f"Linked {len(new_adrs)} new ADRs to ARCHITECTURE.md")

    # 2. Extract "Lessons Learned" from logs (Simulated integration)
    # In a real run, this would read experience_distiller output
    lessons_learned = [
        {"topic": "A11y", "lesson": "Always use aria-label for .card containers to avoid false positives in UX Audit."},
        {"topic": "Go MCP", "lesson": "Go handlers in mcp-server-agent-kit require explicit JSON tag matching for types.ts synchronization."}
    ]
    
    with open(GOTCHAS_FILE, 'r', encoding='utf-8') as f:
        gotchas_content = f.read()
        
    new_lessons = []
    for lesson in lessons_learned:
        if lesson['topic'] not in gotchas_content:
            new_lessons.append(f"### {lesson['topic']}\n{lesson['lesson']}\n")
            
    # 3. Update System Map (Script Inventory) in ARCHITECTURE.md
    scripts_dir = Path(".agent/scripts")
    all_scripts = [f.name for f in scripts_dir.glob("*.py")]
    
    with open(ARCH_FILE, 'r', encoding='utf-8') as f:
        arch_content = f.read()
    
    # Check if scripts are already mentioned
    missing_scripts = []
    for script in all_scripts:
        if script not in arch_content:
            missing_scripts.append(script)
    
    if missing_scripts:
        # We'll append them to the 'Scripts' section in the component map
        # Finding the '├── scripts/' line in ARCHITECTURE.md
        scripts_marker = "├── scripts/"
        if scripts_marker in arch_content:
            # Prepare the new lines to insert
            new_lines = ""
            for script in sorted(missing_scripts):
                new_lines += f"│   ├── {script}    (Auto-registered)\n"
            
            # Insert after the marker
            updated_arch = arch_content.replace(scripts_marker + "\n", scripts_marker + "\n" + new_lines)
            
            with open(ARCH_FILE, 'w', encoding='utf-8') as f:
                f.write(updated_arch)
            updates.append(f"Registered {len(missing_scripts)} new scripts in ARCHITECTURE.md Component Map")

    return {
        "status": "success",
        "updates": updates,
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    result = sync_wiki()
    print(json.dumps(result, indent=2))
