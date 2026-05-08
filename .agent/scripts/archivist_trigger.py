#!/usr/bin/env python3
"""Archivist Trigger – orchestrates the full knowledge‑management pipeline.
Executed automatically after any L2‑L4 orchestration flow.
It runs:
1️⃣ context_pruner.py – cleans the Context Bus.
2️⃣ experience_distiller.py – extracts deep lessons (advanced mode).
3️⃣ adr_drafter.py – drafts ADRs for newly detected architectural shifts.
4️⃣ wiki_sync.py – merges ADRs, lessons, and code changes into the Karpathy‑style Wiki.
"""
import subprocess
import json
import sys
from pathlib import Path

SCRIPTS = [
    "python3 ./.agent/scripts/context_pruner.py",
    "python3 ./.agent/scripts/experience_distiller.py --advanced",
    "python3 ./.agent/scripts/adr_drafter.py",
    "python3 ./.agent/scripts/wiki_sync.py",
    "python3 ./.agent/skills/seo-fundamentals/scripts/seo_checker.py .",
    "python3 ./.agent/scripts/generate_discovery_files.py",
    "python3 ./.agent/scripts/ux_conversion_audit.py .",
    "python3 ./.agent/scripts/social_proof_generator.py",
    "python3 ./.agent/scripts/blue_team_monitor.py",
    "python3 ./.agent/scripts/budget_monitor.py",
    "python3 ./.agent/scripts/chaos_analyzer.py",
    "python3 ./.agent/scripts/hallucination_detector.py",
    "python3 ./.agent/scripts/policy_guardrail.py"
]

results = []
for cmd in SCRIPTS:
    try:
        completed = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=False)
        out = completed.stdout.strip()
        err = completed.stderr.strip()
        results.append({"cmd": cmd, "returncode": completed.returncode, "stdout": out, "stderr": err})
    except Exception as e:
        results.append({"cmd": cmd, "error": str(e)})

print(json.dumps({"status": "completed", "results": results}, indent=2))
