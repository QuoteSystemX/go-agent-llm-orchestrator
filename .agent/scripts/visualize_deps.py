#!/usr/bin/env python3
"""Dependency Visualizer — Scans code imports and generates Mermaid diagrams.
"""
import os
import re
import sys
from pathlib import Path

try:
    from lib.paths import REPO_ROOT
except ImportError:
    sys.path.append(str(Path(__file__).resolve().parent))
    from lib.paths import REPO_ROOT

def scan_python_imports(file_path: Path) -> list[str]:
    try:
        with open(file_path, "r", encoding="utf-8", errors='ignore') as f:
            content = f.read()
        imports = re.findall(r'^\s*(?:from|import)\s+([\w\.]+)', content, re.MULTILINE)
        return [imp.split('.')[0] for imp in imports if not imp.startswith('.')]
    except:
        return []

def scan_go_imports(file_path: Path) -> list[str]:
    try:
        with open(file_path, "r", encoding="utf-8", errors='ignore') as f:
            content = f.read()
        # Find imports in quotes
        imports = re.findall(r'"([^"]+)"', content)
        # Only take local-ish imports or meaningful ones
        return [imp.split('/')[-1] for imp in imports if '/' in imp]
    except:
        return []

def generate_mermaid():
    """Scan the repository and generate a Mermaid dependency graph."""
    edges = set()
    
    # Define interesting modules to track
    interesting = set()
    
    # 1. Scan .agent/scripts
    scripts_dir = REPO_ROOT / ".agent" / "scripts"
    for f in scripts_dir.glob("*.py"):
        interesting.add(f.stem)
        imports = scan_python_imports(f)
        for imp in imports:
            if imp in ["os", "sys", "re", "json", "pathlib", "time", "subprocess", "datetime"]:
                continue
            edges.add(f"  {f.stem} --> {imp}")

    # 2. Scan main project (Go)
    for f in REPO_ROOT.glob("**/*.go"):
        if any(p in str(f) for p in ["vendor", "tmp", ".gemini"]): continue
        src = f.stem
        imports = scan_go_imports(f)
        for imp in imports:
            # Only add if it's part of our project or a key dependency
            edges.add(f"  {src} --> {imp}")

    if not edges:
        return "No local dependencies found."

    mermaid = ["```mermaid", "graph TD"]
    mermaid.extend(sorted(list(edges)))
    mermaid.append("```")
    
    mermaid_str = "\n".join(mermaid)
    
    # Update ARCHITECTURE.md
    arch_path = REPO_ROOT / ".agent" / "ARCHITECTURE.md"
    if arch_path.exists():
        with open(arch_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        marker_start = "<!-- DEPENDENCY_GRAPH_START -->"
        marker_end = "<!-- DEPENDENCY_GRAPH_END -->"
        
        if marker_start in content and marker_end in content:
            new_content = re.sub(
                f"{marker_start}.*?{marker_end}",
                f"{marker_start}\n{mermaid_str}\n{marker_end}",
                content,
                flags=re.DOTALL
            )
            with open(arch_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            return "✅ Mermaid diagram updated in ARCHITECTURE.md."
    
    return f"Generated Mermaid:\n\n{mermaid_str}"

def main():
    print(generate_mermaid())

if __name__ == "__main__":
    main()
