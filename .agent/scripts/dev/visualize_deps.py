#!/usr/bin/env python3
"""Dependency Visualizer — Scans code imports and generates Mermaid diagrams.
"""

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
import sys
from pathlib import Path

try:
    from lib.paths import REPO_ROOT
except ImportError:
    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from lib.paths import REPO_ROOT

def scan_python_imports(file_path: Path) -> list[str]:
    try:
        with open(file_path, "r", encoding="utf-8", errors='ignore') as f:
            lines = f.readlines()
        found = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Basic match for 'import x' or 'from x import y'
            match = re.match(r'^(?:from|import)\s+([\w\.]+)', line)
            if match:
                imp = match.group(1).split('.')[0]
                if imp not in ["os", "sys", "re", "json", "pathlib", "time", "subprocess", "datetime"]:
                    found.append(imp)
        return found
    except:
        return []

def scan_go_imports(file_path: Path) -> list[str]:
    try:
        with open(file_path, "r", encoding="utf-8", errors='ignore') as f:
            content = f.read()
        
        # Strip comments to avoid capturing commented-out imports
        # Strip single-line comments
        content = re.sub(r'//.*', '', content)
        # Strip multi-line comments
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        
        found_imports = []
        
        # Single line: import "pkg" or import alias "pkg"
        single_matches = re.findall(r'import\s+(?:[\w\.]+\s+)?"([^"]+)"', content)
        found_imports.extend(single_matches)
        
        # Block: import ( ... )
        block_matches = re.findall(r'import\s*\((.*?)\)', content, re.DOTALL)
        for block in block_matches:
            quoted_in_block = re.findall(r'"([^"]+)"', block)
            found_imports.extend(quoted_in_block)
            
        # Filter:
        # 1. Only take imports with '/' (excludes stdlib like 'fmt')
        # 2. Prioritize internal project imports if they match a known prefix
        # 3. Limit the total number of imports per file to avoid swelling
        
        project_prefix = "github.com/QuoteSystemX/prompt-library"
        results = []
        for imp in found_imports:
            if '/' not in imp:
                continue
            
            # If it's an internal import, we definitely want it
            if project_prefix in imp:
                # Extract the meaningful part after the prefix
                parts = imp.replace(project_prefix, "").strip("/").split("/")
                if parts and parts[0]:
                    results.append(parts[0])
                else:
                    results.append(imp.split('/')[-1])
            else:
                # For external, only take the last part
                results.append(imp.split('/')[-1])
                
        return list(set(results))[:10] # Limit to 10 unique imports per file
    except Exception:
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

    # Limit total edges to prevent 'swelling' in massive repos
    sorted_edges = sorted(list(edges))
    if len(sorted_edges) > 300:
        sorted_edges = sorted_edges[:300]
        sorted_edges.append("  [...] --> [Limit Reached]")

    mermaid = ["```mermaid", "graph TD"]
    mermaid.extend(sorted_edges)
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
            pattern = f"{re.escape(marker_start)}.*?{re.escape(marker_end)}"
            replacement = f"{marker_start}\n{mermaid_str}\n{marker_end}"
            new_content = re.sub(
                pattern,
                lambda _: replacement,
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
