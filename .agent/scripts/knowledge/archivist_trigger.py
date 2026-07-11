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

    # Real status from subprocess returncodes — not hardcoded
    total = len(results)
    failed = sum(1 for r in results if r.get("returncode", 0) != 0 or r.get("error"))
    if failed == 0:
        status = "completed"
    elif failed < total:
        status = "partial"
    else:
        status = "failed"
    return {"status": status, "results": results, "failed": failed}

if __name__ == "__main__":
    result = run_trigger()
    # STORY-1: Write distillation sentinel so pre-commit hook can verify
    # freshness. The sentinel's mtime is compared to done-story mtimes.
    try:
        from lib.paths import REPO_ROOT
        from datetime import datetime, timezone
        sentinel_dir = REPO_ROOT / ".agent" / "bus"
        sentinel_dir.mkdir(parents=True, exist_ok=True)
        sentinel = sentinel_dir / ".distill_sentinel"
        sentinel.write_text(
            json.dumps({
                "ts": datetime.now(timezone.utc).isoformat(),
                "trigger_status": result.get("status"),
                "failed": result.get("failed", 0),
            }) + "\n",
            encoding="utf-8",
        )
    except Exception as e:
        print(f"⚠️  Could not write distill sentinel: {e}", file=__import__("sys").stderr)

    # STORY-6: Register fresh lessons for re-injection (closes the loop).
    # We re-register any lessons added/modified in this session so the next
    # agent run sees them in its prompt.
    if result.get("status") in ("completed", "partial"):
        try:
            from lib.paths import REPO_ROOT
            sys.path.insert(0, str(REPO_ROOT / ".agent" / "scripts" / "communication"))
            from knowledge_inject import register_lesson  # type: ignore
            from datetime import datetime, timezone
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            register_lesson(today, scope="global", ttl_days=30)
        except Exception as e:
            print(f"⚠️  Could not register today's lessons for re-injection: {e}", file=__import__("sys").stderr)

    print(json.dumps(result, indent=2))
