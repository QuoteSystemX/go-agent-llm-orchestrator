#!/usr/bin/env python3
"""Task Tracer — Automatically links git changes to task cards in tasks/.
"""
import sys
import subprocess
import re
from pathlib import Path
from datetime import datetime

try:
    from lib.paths import REPO_ROOT
    from lib.common import load_json_safe, save_json_atomic
except ImportError:
    sys.path.append(str(Path(__file__).resolve().parent))
    from lib.paths import REPO_ROOT
    from lib.common import load_json_safe, save_json_atomic

def get_staged_files() -> list[str]:
    try:
        res = subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=REPO_ROOT)
        return [f for f in res.decode().split("\n") if f]
    except:
        return []

def find_active_task() -> Path:
    """Find the most recently modified task card in tasks/."""
    tasks_dir = REPO_ROOT / "tasks"
    if not tasks_dir.exists():
        return None
    
    tasks = list(tasks_dir.glob("*.md"))
    if not tasks:
        return None
    
    # Sort by mtime
    tasks.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return tasks[0]

def update_task_card(task_path: Path, files: list[str]):
    content = task_path.read_text(encoding="utf-8")
    
    marker = "## 📂 Измененные файлы"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    file_list = "\n".join([f"- `{f}`" for f in files])
    
    new_entry = f"\n### 📝 Авто-трассировка [{timestamp}]\n{file_list}\n"
    
    if marker in content:
        # Append to existing marker
        content = content.replace(marker, f"{marker}\n{new_entry}")
    else:
        # Add marker at the end
        content += f"\n\n{marker}\n{new_entry}"
    
    task_path.write_text(content, encoding="utf-8")
    return f"✅ Updated task card: {task_path.name}"

def main():
    files = get_staged_files()
    if not files:
        print("No staged files to trace.")
        return

    task = find_active_task()
    if not task:
        print("⚠️  No active task card found in tasks/. Linkage skipped.")
        return

    print(update_task_card(task, files))

if __name__ == "__main__":
    main()
