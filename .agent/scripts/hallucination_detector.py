#!/usr/bin/env python3
"""
Hallucination Detector - AI Safety Audit
Cross-references agent-generated documentation with actual codebase state.
"""
import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parents[2]
BUS_DIR = REPO_ROOT / ".agent" / "bus"

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
