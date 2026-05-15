#!/usr/bin/env python3
"""Obsidian Sync — Wiki-to-Code Bridge & Vault Mirror.

1. Parses [[ObsidianLinks]] in the wiki and maps them to actual code symbols and files.
2. Mirrors knowledge files to an external Obsidian vault for personal knowledge management.
"""

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    import sys
    from pathlib import Path
    REPO_ROOT = Path(__file__).resolve().parents[3]
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))

import os
import re
import json
import shutil
from pathlib import Path
from datetime import datetime

WIKI_DIR = Path("wiki")
CODE_DIRS = [Path("."), Path("internal"), Path("cmd"), Path(".agent/scripts")]
MAP_FILE = Path(".agent/bus/wiki_map.json")

def extract_obsidian_links(text):
    return re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", text)

def find_symbol_in_code(symbol):
    """Simple symbol search in code files (Python and Go)."""
    symbol_clean = re.sub(r'\(.*\)', '', symbol).strip()
    
    matches = []
    for root_dir in CODE_DIRS:
        if not (REPO_ROOT / root_dir).exists(): continue
        for ext in ["py", "go", "md"]:
            for path in (REPO_ROOT / root_dir).rglob(f"*.{ext}"):
                if ".agent/bus" in str(path) or ".git" in str(path): continue
                
                try:
                    with open(path, "r", errors="ignore") as f:
                        content = f.read()
                        if re.search(fr"\b(def|class|func)\s+{symbol_clean}\b", content):
                            matches.append(os.path.relpath(path, REPO_ROOT))
                        elif path.name == symbol_clean or path.stem == symbol_clean:
                            matches.append(os.path.relpath(path, REPO_ROOT))
                except Exception:
                    continue
    return list(set(matches))

def sync_links():
    """Maps wiki links to code symbols."""
    print("🔗 Bridge Team: Syncing Obsidian Wiki links with Codebase...")
    wiki_map = {}
    
    if not (REPO_ROOT / WIKI_DIR).exists():
        print("⚠️ Wiki directory not found. Skipping link sync.")
        return

    for path in (REPO_ROOT / WIKI_DIR).rglob("*.md"):
        with open(path, "r") as f:
            content = f.read()
            links = extract_obsidian_links(content)
            
            for link in links:
                if link not in wiki_map:
                    code_paths = find_symbol_in_code(link)
                    wiki_map[link] = {
                        "mentions_in_wiki": [os.path.relpath(path, REPO_ROOT)],
                        "resolved_code_paths": code_paths
                    }
                else:
                    wiki_map[link]["mentions_in_wiki"].append(os.path.relpath(path, REPO_ROOT))

    os.makedirs(REPO_ROOT / MAP_FILE.parent, exist_ok=True)
    with open(REPO_ROOT / MAP_FILE, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "map": wiki_map
        }, f, indent=2)
    
    print(f"✅ Bridge Team: Link sync complete. {len(wiki_map)} links mapped to code.")

def sync_to_obsidian():
    """Mirrors knowledge to external vault."""
    print("🌉 Bridge Team: Starting Obsidian Vault Mirror Protocol...")
    
    config_path = REPO_ROOT / ".agent" / "config" / "obsidian_config.json"
    if not config_path.exists():
        config = {
            "vault_path": str(REPO_ROOT / "wiki" / "obsidian_vault"),
            "sync_folders": [".agent/knowledge", "wiki/mental-models", "wiki/decisions"],
            "auto_tag": True,
            "add_metadata": True
        }
        os.makedirs(config_path.parent, exist_ok=True)
        with open(config_path, "w") as f:
            json.dump(config, f, indent=4)
    else:
        with open(config_path) as f:
            config = json.load(f)

    vault_path = Path(config["vault_path"])
    os.makedirs(vault_path, exist_ok=True)

    synced_count = 0
    for folder in config["sync_folders"]:
        source_dir = REPO_ROOT / folder
        if not source_dir.exists(): continue
        
        target_dir = vault_path / source_dir.name
        os.makedirs(target_dir, exist_ok=True)
        
        for item in source_dir.glob("*.md"):
            dest_file = target_dir / item.name
            if not dest_file.exists() or item.stat().st_mtime > dest_file.stat().st_mtime:
                content = item.read_text()
                if config["add_metadata"]:
                    header = "---\n"
                    header += f"synced_at: {datetime.now().isoformat()}\n"
                    header += f"source: {folder}/{item.name}\n"
                    if config["auto_tag"]:
                        header += f"tags: [hive, knowledge, {source_dir.name}]\n"
                    header += "---\n\n"
                    content = header + content
                dest_file.write_text(content)
                synced_count += 1

    print(f"✅ Bridge Team: Mirror complete. {synced_count} files mirrored to vault.")

def main():
    sync_links()
    sync_to_obsidian()

if __name__ == "__main__":
    main()
