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
import argparse
import re
from datetime import datetime
from pathlib import Path

from lib.common import render_task_card

REPO_ROOT = Path(__file__).parent.parent.parent.parent

def slugify(text):
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return text.strip('-')

def create_task(task_type, title, epic=None):
    tasks_dir = REPO_ROOT / "tasks"
    tasks_dir.mkdir(exist_ok=True)
    
    today = datetime.now().strftime("%Y-%m-%d")
    slug = slugify(title)
    filename = f"{today}-{slug}.md"
    task_path = tasks_dir / filename
    
    if task_path.exists():
        print(f"Error: Task file {filename} already exists.")
        return
    
    # Template selection: BMAD-lifecycle types (STORY, EPIC, PRD, ...) keep their own dedicated
    # template under wiki-templates/. Anything else (BUG, CHORE, PERF, ...) falls back to the
    # generic ad-hoc TASK_CARD.md — not STORY.md, which is unrelated BMAD/Jules-pipeline content.
    template_name = f"{task_type.upper()}.md"
    template_path = REPO_ROOT / ".agent" / "wiki-templates" / template_name

    if template_path.exists():
        template_content = template_path.read_text(encoding='utf-8')
        content = template_content.replace("[STORY] Story Title", f"[{task_type.upper()}] {title}")
        content = content.replace("Story Title", title)
        if epic:
            content = content.replace("[epic name]", epic)
    else:
        try:
            content = render_task_card(
                tag=task_type.upper(), title=title, agent="TBD", priority="Medium",
                source="task_helper.py",
                problem="Clear description of what was found and why it matters.",
                acceptance_criteria="- [ ] Specific, testable outcome 1\n- [ ] Specific, testable outcome 2",
                context="Any additional context the executing agent needs.",
            )
        except FileNotFoundError:
            # TASK_CARD.md itself missing (e.g. not yet synced to this repo) — degrade to a
            # minimal stub instead of crashing, same safety net the old STORY.md fallback gave.
            content = f"# [{task_type.upper()}] {title}\n\n## Context\n\n## Impact\n\n## Acceptance Criteria\n"

    task_path.write_text(content, encoding='utf-8')
    print(f"✅ Created task: {task_path.relative_to(REPO_ROOT)}")
    return task_path

def main():
    parser = argparse.ArgumentParser(description="Task Helper - Create task cards from templates")
    parser.add_argument("--type", default="STORY", help="Task type (STORY, BUG, FEAT, CHORE, EPIC, etc.)")
    parser.add_argument("--title", required=True, help="Task title")
    parser.add_argument("--epic", help="Epic name")
    
    args = parser.parse_args()
    create_task(args.type, args.title, args.epic)

if __name__ == "__main__":
    main()
