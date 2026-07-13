#!/usr/bin/env python3
"""Pre-commit Reviewer — Checks staged changes against the Lessons Learned database.
"""

# Antigravity Domain-Aware Import Logic
import sys
from pathlib import Path

# Setup unconditional domain-aware path resolution
SCRIPTS_DIR = Path(__file__).resolve().parents[1]  # .agent/scripts
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.append(str(SCRIPTS_DIR))

# Always add domain subfolders to sys.path so direct imports work unconditionally
for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev", "misc"]:
    d_path = str(SCRIPTS_DIR / domain)
    if d_path not in sys.path:
        sys.path.append(d_path)

# Ensure parent directory is also on path
parent_dir = Path(__file__).resolve().parent
if str(parent_dir) not in sys.path:
    sys.path.append(str(parent_dir))

import subprocess

try:
    from lib.paths import REPO_ROOT, LESSONS_PATH
except ImportError:
    # Fallback to absolute/relative resolution
    REPO_ROOT = Path(__file__).resolve().parents[3]
    LESSONS_PATH = REPO_ROOT / "LESSONS_LEARNED.md"

def get_staged_diff() -> str:
    try:
        return subprocess.check_output([
            "git", "diff", "--cached", "--",
            ":(exclude)*.md", ":(exclude)*.json", ":(exclude)*.jsonl",
            ":(exclude)*.yml", ":(exclude)*.html",
        ], cwd=REPO_ROOT).decode("utf-8")
    except Exception:
        return ""

def review_diff():
    diff = get_staged_diff()
    if not diff:
        return True, "No staged changes to review."

    if not LESSONS_PATH.exists():
        return True, "No LESSONS_LEARNED.md found. Skipping review."

    with open(LESSONS_PATH, "r", encoding="utf-8") as f:
        lessons = f.read().lower()

    # Simple heuristic: look for keywords from lessons in the diff
    import re
    # Extract keywords/titles from lessons (simple regex for demo)
    lesson_topics = re.findall(r'### \[\d+-\d+-\d+\] \[\w+\] \[([\w-]+)\] (.*)', lessons)
    
    # Only scan added lines to avoid false positives from removed code
    added_lines = "\n".join(
        l for l in diff.splitlines()
        if l.startswith("+") and not l.startswith("+++")
    ).lower()

    warnings = []
    import re
    for skill, title in lesson_topics:
        # Word-boundary match: \b...\b ensures we match the skill as a
        # whole word, not as a substring (e.g., "test" won't match "testing"
        # or "attestation"). Also skips lines that already had the lesson
        # explicitly suppressed (marked with "# no_lessons_check").
        pattern = re.compile(r"\b" + re.escape(skill) + r"\b")
        if pattern.search(added_lines):
            warnings.append(f"Found mention of skill '{skill}' in diff (Context: {title})")

    if warnings:
        print("\n⚠️  PRE-COMMIT WARNING: Staged changes match known historical issues:")
        for w in warnings:
            print(f"  - {w}")
        print("\nRecommendation: Review LESSONS_LEARNED.md to ensure you aren't repeating past mistakes.")
        return False, "Review finished with warnings."

    # INTEGRATION: Check System Health (Must be > 70 for commit)
    try:
        import status_report
        health = status_report.get_health_report()
        score = health.get("score", 100)
        if score < 70:
            print(f"❌ COMMIT BLOCKED: System Health Score is too low ({score}/100).")
            print("Run 'python3 .agent/scripts/dev/checklist.py . --fix' to improve health.")
            return False, "Low health score."
    except Exception as e:
        print(f"⚠️ Health check skipped: {e}")

    # INTEGRATION: Check Bus Conflicts
    try:
        import conflict_resolver
        res = conflict_resolver.resolve_conflicts()
        if res and "⚠️" in str(res):
            print(f"❌ COMMIT BLOCKED: {res}")
            print("Run 'python3 .agent/scripts/context/conflict_resolver.py' for details.")
            return False, "Bus conflicts detected."
    except Exception as e:
        print(f"⚠️ Conflict check skipped: {e}")

    # INTEGRATION: STRIDE Threat Model — analyze staged diff for security risks
    try:
        import threat_modeler
        threats = threat_modeler.analyze()
        high = [t for t in threats if t.get("severity") == "High" and not t.get("mitigation", "").strip()]
        if high:
            print(f"❌ COMMIT BLOCKED: {len(high)} unmitigated High-severity threat(s) detected.")
            print("Fix or add mitigations, then re-stage.")
            return False, "Unmitigated High-severity threats."
    except Exception as e:
        print(f"⚠️ Threat modeling skipped: {e}")

    # NEW: Automatically trace tasks on successful review
    try:
        import task_tracer
        task_tracer.main()
    except Exception as e:
        print(f"⚠️ Task tracing failed: {e}")

    return True, "Diff looks clean and system is healthy."

if __name__ == "__main__":
    ok, msg = review_diff()
    # Block commit on low health score or active conflicts
    sys.exit(0 if ok else 1)
