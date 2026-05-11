#!/usr/bin/env python3
"""Predictive Watcher — Agentic DevOps.

Detects structural changes in the codebase and suggests/drafts documentation updates.
Part of the Unified Cardinal Enhancements Phase 3.
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
import subprocess
import json
from pathlib import Path

def get_git_changes():
    try:
        # Get staged and unstaged changes
        output = subprocess.check_output(["git", "status", "--porcelain"], stderr=subprocess.STDOUT).decode()
        return [line.strip() for line in output.split("\n") if line.strip()]
    except Exception:
        return []

def analyze_structural_impact(changes):
    impacted = []
    for change in changes:
        status, path = change[:2], change[3:]
        # Detect new directories, scripts, or core modules
        if status == "A " or status == "??":
            if path.endswith(".py") or path.endswith(".go") or "/" in path:
                impacted.append(path)
    return impacted

def draft_adr_suggestion(new_files):
    if not new_files:
        return None
    
    suggestion = f"""
### 🔮 PREDICTIVE WATCHER: Structural Changes Detected
I detected the following new components that might require architectural documentation:

{chr(10).join([f"- {f}" for f in new_files])}

**Proposed Action**:
- Run `python3 .agent/scripts/knowledge/auto_adr_drafter.py` to document these changes.
- Update `ARCHITECTURE.md` with new component descriptions.
"""
    return suggestion

def main():
    print("🔭 Scanning for structural changes...")
    changes = get_git_changes()
    new_files = analyze_structural_impact(changes)
    
    if new_files:
        suggestion = draft_adr_suggestion(new_files)
        print(suggestion)
        
        # Save to bus for the agent to pick up
        bus_dir = Path(".agent/bus/outputs")
        bus_dir.mkdir(parents=True, exist_ok=True)
        
        from datetime import datetime
        event = {
            "timestamp": datetime.now().isoformat(),
            "agent": "predictive-watcher",
            "goal": "Structural change detection",
            "impacted_files": new_files,
            "suggestion": suggestion
        }
        
        filename = f"prediction_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(bus_dir / filename, "w") as f:
            json.dump(event, f, indent=2)
        print(f"📝 Prediction DTO saved to: .agent/bus/outputs/{filename}")

        # Integration with status_report.py (Foresight)
        foresight_dir = Path(".agent/foresight")
        foresight_dir.mkdir(parents=True, exist_ok=True)
        risks = []
        for nf in new_files:
            risks.append({
                "file": nf,
                "risk_score": 50 if nf.endswith(".py") else 30, # Base risk for new scripts
                "description": "New structural component without documented ADR"
            })
        
        with open(foresight_dir / "latest_risk_report.json", "w") as f:
            json.dump(risks, f, indent=2)
    else:
        print("✅ No major structural changes detected.")

if __name__ == "__main__":
    main()
