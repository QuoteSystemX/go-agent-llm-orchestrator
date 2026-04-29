#!/usr/bin/env python3
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
HOOKS_DIR = REPO_ROOT / ".git" / "hooks"
PRE_COMMIT_HOOK = HOOKS_DIR / "pre-commit"

HOOK_CONTENT = """#!/bin/bash
# Antigravity Kit Hygiene Hook
echo "🔍 Running Workspace Hygiene & Validation..."

# Run lint_runner.py in cleanup mode
python3 .agent/skills/lint-and-validate/scripts/lint_runner.py . --cleanup-only

# Run full lint check (without fix to avoid unexpected changes during commit)
python3 .agent/skills/lint-and-validate/scripts/lint_runner.py .

if [ $? -ne 0 ]; then
  echo "❌ Validation failed. Please fix the issues before committing."
  exit 1
fi

echo "✅ Validation passed. Committing..."
exit 0
"""

def install():
    if not (REPO_ROOT / ".git").exists():
        print("❌ Error: Not a git repository.")
        return False

    HOOKS_DIR.mkdir(exist_ok=True)
    
    PRE_COMMIT_HOOK.write_text(HOOK_CONTENT, encoding='utf-8')
    # Make it executable
    os.chmod(PRE_COMMIT_HOOK, 0o755)
    
    print(f"✅ Pre-commit hook installed at: {PRE_COMMIT_HOOK}")
    print("Now all your commits will be automatically validated.")
    return True

if __name__ == "__main__":
    install()
