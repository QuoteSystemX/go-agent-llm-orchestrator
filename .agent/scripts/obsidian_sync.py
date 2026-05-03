#!/usr/bin/env python3
"""Obsidian Sync — Wiki-to-Code Bridge.

Parses [[ObsidianLinks]] in the wiki and maps them to actual code symbols and files.
Enables AI agents to navigate the codebase via the Karpathy Wiki-First methodology.
"""
import os
import re
import json
from pathlib import Path
from datetime import datetime

WIKI_DIR = Path("wiki")
CODE_DIRS = [Path("."), Path("internal"), Path("cmd"), Path(".agent/scripts")]
MAP_FILE = Path(".agent/bus/wiki_map.json")

def extract_obsidian_links(text):
    return re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", text)

def find_symbol_in_code(symbol):
    """Simple symbol search in code files (Python and Go)."""
    # Normalize symbol (e.g., remove function parens)
    symbol_clean = re.sub(r'\(.*\)', '', symbol).strip()
    
    matches = []
    for root_dir in CODE_DIRS:
        for ext in ["py", "go", "md"]:
            for path in root_dir.rglob(f"*.{ext}"):
                if ".agent/bus" in str(path) or ".git" in str(path): continue
                
                try:
                    with open(path, "r", errors="ignore") as f:
                        content = f.read()
                        # Match function/class definitions
                        if re.search(fr"\b(def|class|func)\s+{symbol_clean}\b", content):
                            matches.append(str(path))
                        # Match file names
                        elif path.name == symbol_clean or path.stem == symbol_clean:
                            matches.append(str(path))
                except Exception:
                    continue
    return list(set(matches))

def sync():
    print("🔗 Syncing Obsidian Wiki links with Codebase...")
    wiki_map = {}
    
    if not WIKI_DIR.exists():
        print("⚠️ Wiki directory not found. Skipping sync.")
        return

    # 1. Scan Wiki files
    for path in WIKI_DIR.rglob("*.md"):
        with open(path, "r") as f:
            content = f.read()
            links = extract_obsidian_links(content)
            
            for link in links:
                if link not in wiki_map:
                    code_paths = find_symbol_in_code(link)
                    wiki_map[link] = {
                        "mentions_in_wiki": [str(path)],
                        "resolved_code_paths": code_paths
                    }
                else:
                    wiki_map[link]["mentions_in_wiki"].append(str(path))

    # 2. Save results to Bus
    os.makedirs(MAP_FILE.parent, exist_ok=True)
    with open(MAP_FILE, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "map": wiki_map
        }, f, indent=2)
    
    print(f"✅ Sync complete. {len(wiki_map)} links mapped to code.")
    print(f"📝 Map saved to: {MAP_FILE}")

if __name__ == "__main__":
    sync()
