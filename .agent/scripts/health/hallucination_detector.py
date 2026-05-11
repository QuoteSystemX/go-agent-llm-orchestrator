#!/usr/bin/env python3
"""
Hallucination Detector - AI Safety Audit
Cross-references agent-generated documentation with actual codebase state.
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
import sys
import json
import re
from pathlib import Path
from datetime import datetime

try:
    from lib.paths import REPO_ROOT, BUS_DIR
    from lib.common import load_json_safe
except ImportError:
    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from lib.paths import REPO_ROOT, BUS_DIR
    from lib.common import load_json_safe

def extract_signatures(content: str) -> set[str]:
    """Extract function/method signatures from code."""
    # Matches 'def func_name(args):' or 'func funcName(args)'
    return set(re.findall(r'(?:def|func)\s+([a-zA-Z0-9_]+)', content))

def detect_hallucination(target_file: Path, spec_file: Path) -> list[str]:
    """Compare implementation against spec using semantic boundaries."""
    if not target_file.exists() or not spec_file.exists():
        return ["Error: Target or Spec file missing."]

    target_content = target_file.read_text(encoding="utf-8")
    spec_content = spec_file.read_text(encoding="utf-8")

    discrepancies = []
    
    # 1. Signature Verification
    # If spec mentions a function name, it MUST be in the target
    spec_signatures = extract_signatures(spec_content)
    target_signatures = extract_signatures(target_content)
    
    for sig in spec_signatures:
        if sig not in target_signatures:
            discrepancies.append(f"HALLUCINATION: Function '{sig}' defined in spec but missing in implementation.")

    # 2. Acceptance Criteria (AC) Verification
    ac_matches = re.findall(r'- \[ \] (.*)', spec_content.lower())
    if not ac_matches:
        ac_matches = re.findall(r'^- (.*)', spec_content.lower(), re.MULTILINE)

    target_lower = target_content.lower()
    for ac in ac_matches:
        # Extract keywords
        words = [w for w in re.findall(r'\w+', ac) if len(w) > 4]
        if words and not any(w in target_lower for w in words):
            discrepancies.append(f"MISSING LOGIC: AC '{ac}' not found in implementation (searched for {words[:2]})")

    return discrepancies

def find_script_references(text):
    """Find references to scripts (e.g., script_name.py)."""
    return re.findall(r"[\w\-\.\/]+\.py", text)

def validate_references(refs):
    """Check if referenced files actually exist."""
    results = []
    # Search in common locations
    search_dirs = [REPO_ROOT, REPO_ROOT / ".agent" / "scripts", REPO_ROOT / ".agent" / "scripts" / "lib"]
    
    for ref in refs:
        exists = False
        for d in search_dirs:
            path = d / ref if not ref.startswith("/") else Path(ref)
            if path.exists():
                exists = True
                break
        results.append({"ref": ref, "exists": exists})
    return results

def audit_recent_files():
    """Audit ADRs and Wiki files updated in the last session."""
    flagged = []
    # Focus on docs/adr and wiki/
    targets = list((REPO_ROOT / "docs" / "adr").glob("*.md")) + list((REPO_ROOT / "wiki").glob("*.md"))
    
    for target in targets:
        # Only check files updated recently (heuristic: last 10 mins)
        mtime = os.path.getmtime(target)
        if (datetime.now().timestamp() - mtime) < 600:
            content = target.read_text()
            refs = find_script_references(content)
            validations = validate_references(refs)
            
            invalid = [v["ref"] for v in validations if not v["exists"]]
            if invalid:
                flagged.append({
                    "file": str(target.relative_to(REPO_ROOT)),
                    "hallucinated_scripts": invalid
                })
    return flagged

def main():
    print(f"\n{'='*60}")
    print(f"⚖️  HALLUCINATION DETECTOR - Truth Engine")
    print(f"{'='*60}")
    
    flagged = audit_recent_files()
    
    if flagged:
        print("🔴 ALERT: Hallucinations detected!")
        for item in flagged:
            print(f"   📄 File: {item['file']}")
            for script in item['hallucinated_scripts']:
                print(f"      ❌ Ghost Script: {script}")
    else:
        print("✅ No hallucinations detected in recent documents.")

    # Export for status_report
    BUS_DIR.mkdir(parents=True, exist_ok=True)
    with open(BUS_DIR / "hallucination_report.json", "w") as f:
        json.dump({
            "status": "FLAGGED" if flagged else "PASS",
            "flagged_items": flagged,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }, f, indent=2)

if __name__ == "__main__":
    main()
