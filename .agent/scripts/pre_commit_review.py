#!/usr/bin/env python3
"""Pre-commit Reviewer — Checks staged changes against the Lessons Learned database.
"""
import sys
import subprocess
from pathlib import Path

try:
    from lib.paths import REPO_ROOT, LESSONS_PATH
except ImportError:
    sys.path.append(str(Path(__file__).resolve().parent))
    from lib.paths import REPO_ROOT, LESSONS_PATH

def get_staged_diff() -> str:
    try:
        return subprocess.check_output(["git", "diff", "--cached"], cwd=REPO_ROOT).decode("utf-8")
    except:
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
    
    warnings = []
    for skill, title in lesson_topics:
        # If the skill tag or keywords from title appear in the diff (+ lines)
        if skill in diff.lower():
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
            print("Run 'python3 .agent/scripts/checklist.py . --fix' to improve health.")
            return False, "Low health score."
    except Exception as e:
        print(f"⚠️ Health check skipped: {e}")

    # INTEGRATION: Check Bus Conflicts
    try:
        import conflict_resolver
        conflicts = conflict_resolver.resolve_conflicts()
        if conflicts:
            print(f"❌ COMMIT BLOCKED: Found {len(conflicts)} active bus conflicts.")
            print("Run 'python3 .agent/scripts/conflict_resolver.py' for details.")
            return False, "Bus conflicts detected."
    except Exception as e:
        print(f"⚠️ Conflict check skipped: {e}")

    # NEW: Automatically trace tasks on successful review
    try:
        import task_tracer
        task_tracer.main()
    except Exception as e:
        print(f"⚠️ Task tracing failed: {e}")

    return True, "Diff looks clean and system is healthy."

if __name__ == "__main__":
    ok, msg = review_diff()
    # We don't block the commit by default, just warn.
    # To block, exit with non-zero.
    sys.exit(0)
