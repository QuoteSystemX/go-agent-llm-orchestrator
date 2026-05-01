#!/usr/bin/env python3
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent

def run_post_mortem(task_file):
    print(f"🕵️ Analyzing failure for task: {task_file}")
    
    # Read the task file and its history
    task_path = REPO_ROOT / "tasks" / task_file
    if not task_path.exists():
        print(f"Error: Task file {task_file} not found.")
        return

    # In a real agentic flow, we would extract logs here.
    # For now, we prepare the context for the Analyst.
    
    print("\n--- POST-MORTEM CONTEXT PREPARED ---")
    print(f"Task: {task_file}")
    print("Action Required: Invoke @analyst to extract 'Lesson Learned' in this format:")
    print(f"### [{datetime.now().strftime('%Y-%m-%d')}] [TAG] Title")
    print("- Context: ...")
    print("- Root Cause: ...")
    print("- Prevention: ...")
    print("Then update .agent/rules/LESSONS_LEARNED.md")
    print("------------------------------------\n")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 post_mortem_runner.py <task_filename>")
        sys.exit(1)
        
    run_post_mortem(sys.argv[1])
