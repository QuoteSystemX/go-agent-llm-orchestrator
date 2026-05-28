#!/usr/bin/env python3
"""Predictive Watcher — Agentic DevOps.

Detects structural changes in the codebase and drafts ADR suggestions.
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
from datetime import datetime
from pathlib import Path

# All git porcelain v1 status codes that indicate a structural change
STRUCTURAL_STATUSES = {"A ", "??", "M ", "D ", "R ", "MM", "AM", "RM", "AD", "MD"}
MONITORED_EXTENSIONS = {".py", ".go", ".ts", ".tsx", ".js", ".yaml", ".yml"}


def get_git_changes() -> list[str]:
    try:
        output = subprocess.check_output(
            ["git", "status", "--porcelain"], stderr=subprocess.STDOUT
        ).decode()
        return [line for line in output.split("\n") if line.strip()]
    except Exception:
        return []


def analyze_structural_impact(changes: list[str]) -> list[dict]:
    """Return impacted file entries for all structural git status codes.

    Each entry: {"path": str, "status": str}
    Handles porcelain R  format (tab-separated old->new paths).
    """
    impacted = []
    for change in changes:
        if len(change) < 3:
            continue
        status = change[:2]
        raw_path = change[3:]

        if status not in STRUCTURAL_STATUSES:
            continue

        # Renamed files: "R  old_path\tnew_path" — take the new path
        if "\t" in raw_path:
            raw_path = raw_path.split("\t")[-1]

        path = raw_path.strip()
        if Path(path).suffix in MONITORED_EXTENSIONS or "/" in path:
            impacted.append({"path": path, "status": status.strip()})

    return impacted


def draft_adr_suggestion(impacted: list[dict]) -> str | None:
    """Attempt to draft an ADR via auto_adr_drafter; fall back to template."""
    if not impacted:
        return None

    file_list = "\n".join(f"- [{e['status']}] {e['path']}" for e in impacted)
    conflict_desc = (
        f"Structural changes detected in {len(impacted)} file(s):\n{file_list}"
    )

    # Try to call the real ADR drafter
    try:
        from knowledge.auto_adr_drafter import draft_adr  # type: ignore
        draft = draft_adr(conflict_desc)
        if draft:
            return draft
    except Exception:
        pass

    # Graceful fallback template
    return (
        f"### PREDICTIVE WATCHER: Structural Changes Detected\n\n"
        f"{conflict_desc}\n\n"
        "**Proposed Action**: Run `python3 .agent/scripts/knowledge/auto_adr_drafter.py`"
        " to document these changes and update `ARCHITECTURE.md`."
    )


def main():
    print("🔭 Scanning for structural changes...")
    changes = get_git_changes()
    impacted = analyze_structural_impact(changes)

    if impacted:
        suggestion = draft_adr_suggestion(impacted)
        print(suggestion)

        bus_dir = Path(".agent/bus/outputs")
        bus_dir.mkdir(parents=True, exist_ok=True)

        event = {
            "timestamp": datetime.now().isoformat(),
            "agent": "predictive-watcher",
            "goal": "Structural change detection",
            "impacted_files": [e["path"] for e in impacted],
            "impacted": impacted,
            "suggestion": suggestion,
        }

        filename = f"prediction_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(bus_dir / filename, "w") as f:
            json.dump(event, f, indent=2)
        print(f"📝 Prediction DTO saved to: .agent/bus/outputs/{filename}")

        foresight_dir = Path(".agent/foresight")
        foresight_dir.mkdir(parents=True, exist_ok=True)
        risks = [
            {
                "file": e["path"],
                "status": e["status"],
                "risk_score": 50 if e["path"].endswith(".py") else 30,
                "description": "Structural change without documented ADR",
            }
            for e in impacted
        ]
        with open(foresight_dir / "latest_risk_report.json", "w") as f:
            json.dump(risks, f, indent=2)
    else:
        print("✅ No major structural changes detected.")


if __name__ == "__main__":
    main()
