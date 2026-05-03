#!/usr/bin/env python3
"""Knowledge Miner (The Archeologist).

Scans the codebase for 'undocumented clusters' and proposes Karpathy-style
Mental Models for the Wiki. Supports the Hybrid Knowledge Governance protocol.
"""
import os
import json
import sys
from pathlib import Path

WIKI_MAP = Path(".agent/bus/wiki_map.json")
WIKI_DIR = Path("wiki/mental-models")
PROPOSALS_DIR = Path("wiki/proposals")

def load_wiki_map():
    if not WIKI_MAP.exists():
        return {"map": {}}
    with open(WIKI_MAP, "r") as f:
        return json.load(f)

def get_undocumented_files(wiki_map):
    mapped_files = []
    for link_data in wiki_map.get("map", {}).values():
        mapped_files.extend(link_data.get("resolved_code_paths", []))
    
    undocumented = []
    # Scan project root and key folders
    for root, dirs, files in os.walk("."):
        if any(x in root for x in [".git", ".agent", "node_modules", "vendor", "dist", "build"]):
            continue
            
        for file in files:
            if file.endswith((".py", ".go", ".js", ".ts", ".md")):
                path = os.path.relpath(os.path.join(root, file), ".")
                if path not in mapped_files and not path.startswith("wiki/"):
                    undocumented.append(path)
    return undocumented

def propose_mental_model(file_cluster):
    """Heuristic for generating a mental model proposal."""
    # In a real scenario, this would be an LLM call.
    # Here we group by folder and suggest a model for the folder.
    folders = {}
    for f in file_cluster:
        folder = os.path.dirname(f) or "root"
        if folder not in folders: folders[folder] = []
        folders[folder].append(f)
        
    proposals = []
    for folder, files in folders.items():
        if len(files) < 2: continue # Only group clusters
        
        proposal_name = folder.replace("/", "-").capitalize()
        proposal_path = PROPOSALS_DIR / f"PROPOSAL-{proposal_name}.md"
        
        content = f"""# [PROPOSAL]: Mental Model for '{folder}'

## 🎯 Observed Intent
Based on files like {', '.join(files[:3])}, this cluster seems to handle **{folder} logic**.

## 🗝️ Core Principles (Inferred)
1. **Modular Design**: Files are organized within the '{folder}' namespace.
2. **Component Separation**: Logic is isolated from the root.

## 🔗 Related Components
{chr(10).join([f"- [[{os.path.basename(f)}]]" for f in files])}

## 📖 Action Required
Please review this proposal in Obsidian and move it to `wiki/mental-models/` if accurate.
"""
        os.makedirs(PROPOSALS_DIR, exist_ok=True)
        with open(proposal_path, "w") as f:
            f.write(content)
        proposals.append(str(proposal_path))
    
    return proposals

def run_audit():
    print("🔍 Running Knowledge Audit (Retroactive Mode)...")
    wiki_map = load_wiki_map()
    undocumented = get_undocumented_files(wiki_map)
    
    if not undocumented:
        print("✅ All code is documented in the Wiki Knowledge Graph!")
        return
        
    print(f"⚠️ Found {len(undocumented)} undocumented files.")
    proposals = propose_mental_model(undocumented)
    
    if proposals:
        print(f"📝 Generated {len(proposals)} Mental Model proposals in {PROPOSALS_DIR}/")
        for p in proposals:
            print(f"   - {p}")
    else:
        print("ℹ️ No significant undocumented clusters found (groups of 2+ files).")

if __name__ == "__main__":
    run_audit()
