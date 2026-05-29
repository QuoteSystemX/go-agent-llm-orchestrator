#!/usr/bin/env python3

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
import subprocess
import logging
import re
from pathlib import Path
from lib.suppress import suppress

logger = logging.getLogger(__name__)


def _run_lint(path: str) -> list[dict]:
    """Run ruff on a file and return list of (line, col, message) issues."""
    issues = []
    with suppress("ci_auto_fixer.ruff", level=logging.WARNING):
        res = subprocess.run(
            ["python3", "-m", "ruff", "check", "--output-format=text", path],
            capture_output=True, text=True, timeout=30,
        )
        for line in res.stdout.splitlines():
            m = re.match(r"(.+):(\d+):(\d+):\s+(\S+)\s+(.*)", line)
            if m:
                issues.append({
                    "file": m.group(1),
                    "line": int(m.group(2)),
                    "col": int(m.group(3)),
                    "code": m.group(4),
                    "message": m.group(5).strip(),
                })
    return issues


def _apply_auto_fix(path: str) -> bool:
    """Try to auto-fix with ruff --fix. Returns True if any fixes applied."""
    with suppress("ci_auto_fixer.ruff_fix", level=logging.WARNING):
        res = subprocess.run(
            ["python3", "-m", "ruff", "check", "--fix", path],
            capture_output=True, text=True, timeout=30,
        )
        fixed = "Fixed" in res.stdout or res.returncode == 0
        return fixed
    return False


def run_auto_fix():
    print("🚑 CI Failure detected. Starting Autonomous Healing...")

    # Discover changed Python files
    changed_files = []
    with suppress("ci_auto_fixer.git_diff", level=logging.DEBUG):
        changed_files = subprocess.check_output(
            ["git", "diff", "--name-only", "HEAD~1"],
            cwd=Path.cwd(), text=True,
        ).splitlines()
        changed_files = [f for f in changed_files if f.endswith(".py")]

    if not changed_files:
        print("ℹ️ No changed Python files detected. Falling back to full scan.")
        changed_files = sorted(Path(".agent/scripts").rglob("*.py"))[:20]

    issues_found = 0
    auto_fixes = 0

    for f in changed_files:
        fp = str(f)
        issues = _run_lint(fp)
        if issues:
            issues_found += len(issues)
            print(f"  🐛 {fp}: {len(issues)} issue(s)")
            for i in issues[:3]:
                print(f"    {i['code']}:{i['line']} — {i['message'][:80]}")
            if len(issues) > 3:
                print(f"    ... and {len(issues) - 3} more")

            # Try auto-fix for auto-fixable issues
            if _apply_auto_fix(fp):
                auto_fixes += 1
                print(f"    ✅ Auto-fix applied")

    # Create task card only for non-trivial issues (not auto-fixable)
    remaining = issues_found - auto_fixes
    if remaining > 0:
        task_path = Path("tasks/ci-auto-fix-needed.md")
        details = "\n".join(
            f"- `{Path(fp).name}`: {cnt} issue(s)"
            for fp in changed_files
            if (cnt := len(_run_lint(str(fp)))) > 0
        )
        task_content = (
            f"# [BUG] Autonomous Fix: CI Regression\n"
            f"## Context\n"
            f"{issues_found} lint issues detected, {auto_fixes} auto-fixed.\n"
            f"{remaining} remaining.\n\n"
            f"## Files\n{details}\n"
        )
        task_path.write_text(task_content)
        print(f"📂 Created task for remaining issues: {task_path}")
    else:
        print("✅ All issues auto-fixed or none found.")

    print(f"\n[HEALING COMPLETE] {issues_found} issues, {auto_fixes} auto-fixed, {remaining} remaining")

if __name__ == "__main__":
    run_auto_fix()
