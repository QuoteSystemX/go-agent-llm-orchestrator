#!/usr/bin/env python3

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
import re
from pathlib import Path

def validate_obsidian_links():
    wiki_dir = Path("wiki")
    if not wiki_dir.exists():
        print("⚠️  Wiki directory not found.")
        return

    all_files = list(wiki_dir.glob("**/*.md"))
    file_names = {f.stem for f in all_files}
    
    orphan_files = set(file_names)
    broken_links = []
    
    # Exclude index/main files from being orphans
    orphan_files.discard("index")
    orphan_files.discard("ROADMAP")
    orphan_files.discard("README")

    for file_path in all_files:
        content = file_path.read_text(encoding="utf-8")
        
        # Find [[links]]
        links = re.findall(r"\[\[(.*?)\]\]", content)
        for link in links:
            # Handle [[Link|Alias]] or [[Link#Section]]
            target = link.split("|")[0].split("#")[0].strip()
            if target and target not in file_names:
                broken_links.append((file_path.name, target))
            
            # If a file is linked, it's not an orphan
            if target in orphan_files:
                orphan_files.remove(target)

    print("\n--- Obsidian Knowledge Graph Audit ---")
    
    if broken_links:
        print("❌ Broken Links Found:")
        for source, target in broken_links:
            print(f"  - {source} -> [[{target}]] (Target missing)")
    else:
        print("✅ No broken links found.")

    if orphan_files:
        print("⚠️  Orphan Files (No incoming links):")
        for orphan in sorted(orphan_files):
            print(f"  - {orphan}.md")
    else:
        print("✅ No orphan files found.")
    
    print("--------------------------------------\n")

if __name__ == "__main__":
    validate_obsidian_links()
