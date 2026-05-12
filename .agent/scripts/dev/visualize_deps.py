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
            content = f.read()
        imports = re.findall(r'^\s*(?:from|import)\s+([\w\.]+)', content, re.MULTILINE)
        return [imp.split('.')[0] for imp in imports if not imp.startswith('.')]
    except:
        return []

def scan_go_imports(file_path: Path) -> list[str]:
    try:
        with open(file_path, "r", encoding="utf-8", errors='ignore') as f:
            content = f.read()
        
        # More robust Go import scanning:
        # 1. Single line imports: import "..."
        # 2. Block imports: import ( ... )
        
        found_imports = []
        
        # Single line: import "pkg" or import alias "pkg"
        single_matches = re.findall(r'import\s+(?:[\w\.]+\s+)??"([^"]+)"', content)
        found_imports.extend(single_matches)
        
        # Block: import ( ... )
        block_matches = re.findall(r'import\s*\((.*?)\)', content, re.DOTALL)
        for block in block_matches:
            # Extract quoted strings from the block
            quoted_in_block = re.findall(r'"([^"]+)"', block)
            found_imports.extend(quoted_in_block)
            
        # Filter for local project imports (usually contain /) or meaningful ones
        # and extract the last part of the path
        return [imp.split('/')[-1] for imp in found_imports if '/' in imp]
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
