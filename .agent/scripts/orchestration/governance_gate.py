#!/usr/bin/env python3
"""Governance Gate (The Sentinel).

Enforces the 'Proactive Documentation' rule: new files must be defined in the
Wiki (Stories or ADRs) before implementation.
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
import os
import re
import json
from pathlib import Path

WIKI_STORIES = Path("wiki/stories")
WIKI_ADR = Path("wiki/decisions")

def is_file_in_wiki(file_path):
    # Check all stories and ADRs for the file path
    for wiki_dir in [WIKI_STORIES, WIKI_ADR]:
        if not wiki_dir.exists(): continue
        for path in wiki_dir.rglob("*.md"):
            with open(path, "r", errors="ignore") as f:
                content = f.read()
                if file_path in content or os.path.basename(file_path) in content:
                    return True
    return False

def run_auditor(script_name, target):
    """Run a specialized auditor script and return success status."""
    scripts_dir = Path(__file__).resolve().parent.parent / "health"
    script_path = scripts_dir / script_name
    try:
        res = subprocess.run([sys.executable, str(script_path), str(target)], capture_output=True, text=True)
        return res.returncode == 0, res.stdout
    except:
        return False, "Execution Error"

def check_governance(impacted_files):
    print("🛡️  Activating Sentinel Governance Gate...")
    
    overall_success = True
    for f in impacted_files:
        print(f"  🔍 Auditing '{f}'...")
        
        # 1. Wiki-First Compliance (for new files)
        if not os.path.exists(f) or os.path.getsize(f) == 0:
            if not is_file_in_wiki(f):
                print(f"    ❌ GOVERNANCE VETO: No Wiki definition for '{f}'")
                overall_success = False

        # 2. Alignment Oracle Check
        aligned, msg = run_auditor("alignment_oracle.py", f)
        if not aligned:
            print(f"    🔮 ALIGNMENT WARNING: Potential debt in '{f}'\n{msg}")
            # We allow for now, but log warning

        # 3. Policy Guardrail (Design/Security)
        compliant, msg = run_auditor("policy_guardrail.py", f)
        if not compliant:
            print(f"    🛑 POLICY VIOLATION in '{f}':\n{msg}")
            overall_success = False

    if not overall_success:
        print("\n❌ SENTINEL VETO: Implementation blocked due to governance violations.")
        return False
        
    print("✅ Governance check passed. Integrity confirmed.")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 governance_gate.py <impacted_files_json>")
        sys.exit(1)
        
    impacted_files = json.loads(sys.argv[1])
    success = check_governance(impacted_files)
    sys.exit(0 if success else 1)
