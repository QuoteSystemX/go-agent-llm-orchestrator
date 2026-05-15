#!/usr/bin/env python3
"""
Agent Squeeze — High-integrity knowledge distillation.
======================================================
The "Active Squeeze" tool. Designed to be run by the agent at the end of a session.
Analyzes context, extracts insights, and updates both local and global knowledge.
"""

import sys
import subprocess
import json
import re
from pathlib import Path
from datetime import datetime, timedelta

# Antigravity Path Resolution
try:
    from lib.paths import REPO_ROOT, LESSONS_PATH, GLOBAL_LESSONS_PATH, ARCHIVE_DIR
    from lib.common import load_json_safe
except ImportError:
    SCRIPTS_DIR = Path(__file__).resolve().parents[1]
    sys.path.append(str(SCRIPTS_DIR))
    from lib.paths import REPO_ROOT, LESSONS_PATH, GLOBAL_LESSONS_PATH, ARCHIVE_DIR
    from lib.common import load_json_safe

def get_git_summary():
    """Extract changes from the current session."""
    try:
        # Get diff of current changes (staged or unstaged)
        diff = subprocess.check_output(["git", "diff", "HEAD"], cwd=str(REPO_ROOT), text=True)
        # Get last 3 commit messages
        logs = subprocess.check_output(["git", "log", "-n", "3", "--pretty=%B"], cwd=str(REPO_ROOT), text=True)
        return diff, logs
    except:
        return "", ""

def format_lesson(type_tag: str, skill_tag: str, insight: str) -> str:
    """Format insight into standard markdown entry."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    return f"### [{date_str}] [{type_tag}] [{skill_tag}] {insight}"

def update_local_lessons(lesson: str):
    """Append lesson to local LESSONS_LEARNED.md."""
    if not LESSONS_PATH.parent.exists():
        LESSONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    content = ""
    if LESSONS_PATH.exists():
        content = LESSONS_PATH.read_text(encoding="utf-8")
    
    if lesson.strip() in content:
        print("ℹ️ Lesson already exists in local file.")
        return

    with open(LESSONS_PATH, "a", encoding="utf-8") as f:
        f.write(f"\n{lesson}\n")
    print(f"✅ Local lessons updated: {LESSONS_PATH}")

def update_global_brain(lesson: str):
    """Directly push lesson to global knowledge hub if possible."""
    if not GLOBAL_LESSONS_PATH.parent.exists():
        GLOBAL_LESSONS_PATH.parent.mkdir(parents=True, exist_ok=True)
        
    with open(GLOBAL_LESSONS_PATH, "a", encoding="utf-8") as f:
        f.write(f"\n{lesson}\n")
    print(f"🧠 Global Brain updated: {GLOBAL_LESSONS_PATH}")

def run_archiving():
    """Archive old lessons (Logic migrated from experience_distiller.py)."""
    # Import locally to avoid circular deps if any
    import experience_distiller
    result = experience_distiller.distill_lessons()
    print(f"📦 Archiving: {result}")

def main():
    print("🍋 Starting Agentic Squeeze (Knowledge Extraction)...")
    
    # 1. Automatic Context Extraction
    diff, logs = get_git_summary()
    
    if "--insight" not in sys.argv:
        print("⚠️ No insight provided via --insight. Please describe what you learned.")
        print("Example usage: python3 agent_squeeze.py --type FIX --skill go-patterns --insight 'Use (instance, error) instead of panics'")
        sys.exit(1)
        
    type_tag = "INFO"
    skill_tag = "general"
    insight = "New lesson learned."
    
    def _arg_value(flag: str) -> str | None:
        idx = sys.argv.index(flag)
        return sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None

    if "--type" in sys.argv:
        type_tag = _arg_value("--type") or type_tag
    if "--skill" in sys.argv:
        skill_tag = _arg_value("--skill") or skill_tag
    if "--insight" in sys.argv:
        insight = _arg_value("--insight") or insight

    lesson = format_lesson(type_tag, skill_tag, insight)
    
    # 2. Update Knowledge
    update_local_lessons(lesson)
    
    if "--global" in sys.argv:
        update_global_brain(lesson)
        
    # 3. Cleanup & Maintenance
    run_archiving()
    
    print("✅ Squeeze complete. Knowledge base is fresh.")

if __name__ == "__main__":
    main()
