#!/usr/bin/env python3
"""Alignment Oracle — Predicts long-term impact of decisions on project health.
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

import sys
import re
import subprocess
import json
from pathlib import Path

def check_complexity(file_path: Path) -> list[str]:
    """Check code complexity using radon (if available) or manual metrics."""
    warnings = []
    try:
        # Use radon for cyclomatic complexity
        res = subprocess.run(["radon", "cc", str(file_path), "-s", "--json"], capture_output=True, text=True)
        if res.returncode == 0 and res.stdout.strip():
            data = json.loads(res.stdout)
            for file_data in data.values():
                for block in file_data:
                    if block.get('complexity', 0) > 10:
                        warnings.append(f"🧠 HIGH COMPLEXITY: Block '{block['name']}' has CC={block['complexity']} (limit 10).")
    except:
        # Fallback: manual line count per function
        content = file_path.read_text()
        functions = re.findall(r'def\s+\w+\(.*?\):', content)
        if len(content.splitlines()) > 300:
            warnings.append("📏 FILE LENGTH: Module is too large (>300 lines), suggest splitting.")
            
    return warnings

def check_dna_alignment(content: str) -> list[str]:
    """Verify alignment with User DNA (PRAGMATIC / MINIMALIST)."""
    warnings = []
    # If minimalist, excessive comments are a 'debt'
    comment_ratio = len(re.findall(r'#.*', content)) / (len(content.splitlines()) + 1)
    if comment_ratio > 0.4:
        warnings.append("💬 DNA MISALIGNMENT: Excessive comments for a 'MINIMALIST' profile.")
        
    if "try:" in content and "except:" in content and "pass" in content:
        warnings.append("🩹 SILENT FAILURE: 'except: pass' detected. Violates reliability protocol.")
        
    return warnings

def main():
    if len(sys.argv) < 2:
        print("Usage: alignment_oracle.py <file_to_audit>")
        sys.exit(1)
        
    target = Path(sys.argv[1])
    print(f"🔮 Consulting Advanced Alignment Oracle for '{target.name}'...")
    
    content = target.read_text(encoding="utf-8")
    warnings = []
    warnings.extend(check_complexity(target))
    warnings.extend(check_dna_alignment(content))
    
    # Keyword markers from v1
    debt_markers = {"HACK": "Hack", "TODO": "Todo", "FIXME": "Fixme", "bypass": "Bypass"}
    for m, label in debt_markers.items():
        if m.lower() in content.lower():
            warnings.append(f"🚩 DEBT MARKER: {label} found.")

    if warnings:
        print("🛑 ALIGNMENT WARNINGS FOUND:")
        for w in warnings:
            print(f"  {w}")
        sys.exit(2)
    else:
        print("✅ Architecture is perfectly aligned.")

if __name__ == "__main__":
    main()
