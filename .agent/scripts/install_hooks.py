#!/usr/bin/env python3
"""Install Hooks — Activates the Antigravity Kit git hooks.
"""
import sys
import os
import shutil
from pathlib import Path

try:
    from lib.paths import REPO_ROOT
except ImportError:
    sys.path.append(str(Path(__file__).resolve().parent))
    from lib.paths import REPO_ROOT

PRE_COMMIT_CONTENT = """#!/bin/bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
# Review staged changes against historical lessons
python3 "$REPO_ROOT/.agent/scripts/pre_commit_review.py"
STATUS=$?
if [ $STATUS -ne 0 ]; then
    echo "❌ pre-commit review failed. Fix issues or use --no-verify to skip."
    exit $STATUS
fi
# Link staged files to the active task card
python3 "$REPO_ROOT/.agent/scripts/task_tracer.py" 2>/dev/null || true
exit 0
"""

def install_pre_commit():
    git_hooks_dir = REPO_ROOT / ".git" / "hooks"
    if not git_hooks_dir.exists():
        print("❌ .git/hooks directory not found. Is this a git repository?")
        return False

    hook_path = git_hooks_dir / "pre-commit"
    with open(hook_path, "w", encoding="utf-8") as f:
        f.write(PRE_COMMIT_CONTENT)
    os.chmod(hook_path, 0o755)
    print(f"✅ Installed pre-commit hook → pre_commit_review.py + task_tracer.py")
    return True

if __name__ == "__main__":
    if install_pre_commit():
        print("✨ Hooks activated successfully.")
    else:
        sys.exit(1)
