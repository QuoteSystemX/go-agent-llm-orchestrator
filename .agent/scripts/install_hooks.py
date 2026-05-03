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

def install_pre_commit():
    git_hooks_dir = REPO_ROOT / ".git" / "hooks"
    if not git_hooks_dir.exists():
        print("❌ .git/hooks directory not found. Is this a git repository?")
        return False
    
    hook_path = git_hooks_dir / "pre-commit"
    reviewer_script = REPO_ROOT / ".agent" / "scripts" / "pre_commit_review.py"
    
    # Use a portable path so the hook works for any developer / CI checkout
    content = """#!/bin/bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
python3 "$REPO_ROOT/.agent/scripts/pre_commit_review.py"
"""
    
    with open(hook_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    # Make executable
    os.chmod(hook_path, 0o755)
    print(f"✅ Installed pre-commit hook at {hook_path}")
    return True

if __name__ == "__main__":
    if install_pre_commit():
        print("✨ Hooks activated successfully.")
    else:
        sys.exit(1)
