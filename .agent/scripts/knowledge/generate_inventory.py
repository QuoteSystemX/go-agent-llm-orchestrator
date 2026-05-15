#!/usr/bin/env python3
import os
from pathlib import Path

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    import sys
    REPO_ROOT = Path(__file__).resolve().parents[3]
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))

def generate_inventory():
    """Generates an exhaustive list of all code files in the repository."""
    output_file = REPO_ROOT / ".agent" / "knowledge" / "inventory.md"
    
    code_extensions = {".py", ".go", ".js", ".ts", ".tsx", ".html", ".css", ".md"}
    exclude_dirs = {".git", "node_modules", "venv", "__pycache__", "dist", "build", "scratch", "obsidian_vault"}
    
    inventory = [
        "# Codebase Inventory",
        "",
        "This document provides an exhaustive list of all code files in the repository to ensure full KI coverage and semantic awareness.",
        "",
        "## Indexed Files",
        ""
    ]
    
    # Unified scan
    all_files = []
    for root, dirs, files in os.walk(REPO_ROOT):
        # Skip excluded dirs
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        rel_root = os.path.relpath(root, REPO_ROOT)
        if rel_root == ".": rel_root = ""
        
        for file in files:
            if any(file.endswith(ext) for ext in code_extensions):
                path = os.path.join(rel_root, file).replace("./", "")
                if path.startswith("/"): path = path[1:]
                all_files.append(path)
    
    for path in sorted(all_files):
        inventory.append(f"- `{path}`")
            
    os.makedirs(output_file.parent, exist_ok=True)
    output_file.write_text("\n".join(inventory))
    print(f"✅ Inventory generated at {output_file}")

if __name__ == "__main__":
    generate_inventory()
