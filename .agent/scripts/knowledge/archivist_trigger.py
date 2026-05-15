#!/usr/bin/env python3
"""Archivist Trigger – orchestrates the full knowledge‑management pipeline.
Executed automatically after any L2‑L4 orchestration flow.
It runs:
1️⃣ context_pruner.py – cleans the Context Bus.
2️⃣ experience_distiller.py – extracts deep lessons (advanced mode).
3️⃣ adr_drafter.py – drafts ADRs for newly detected architectural shifts.
4️⃣ wiki_sync.py – merges ADRs, lessons, and code changes into the Karpathy‑style Wiki.
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

import subprocess
import json
import sys
from pathlib import Path

SCRIPTS = [
    "python3 ./.agent/scripts/context/context_pruner.py",
    "python3 ./.agent/scripts/knowledge/experience_distiller.py --advanced",
    "python3 ./.agent/scripts/knowledge/adr_drafter.py",
    "python3 ./.agent/scripts/knowledge/wiki_sync.py",
    "python3 ./.agent/skills/seo-fundamentals/scripts/seo_checker.py .",
    "python3 ./.agent/scripts/misc/generate_discovery_files.py",
    "python3 ./.agent/scripts/analysis/ux_conversion_audit.py .",
    "python3 ./.agent/scripts/delivery/social_proof_generator.py",
    "python3 ./.agent/scripts/health/blue_team_monitor.py",
    "python3 ./.agent/scripts/health/budget_monitor.py",
    "python3 ./.agent/scripts/chaos/chaos_analyzer.py",
    "python3 ./.agent/scripts/health/hallucination_detector.py",
    "python3 ./.agent/scripts/health/policy_guardrail.py"
]

def run_trigger():
    results = []
    for cmd in SCRIPTS:
        try:
            completed = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=False)
            out = completed.stdout.strip()
            err = completed.stderr.strip()
            results.append({"cmd": cmd, "returncode": completed.returncode, "stdout": out, "stderr": err})
        except Exception as e:
            results.append({"cmd": cmd, "error": str(e)})

    return {"status": "completed", "results": results}

if __name__ == "__main__":
    print(json.dumps(run_trigger(), indent=2))
