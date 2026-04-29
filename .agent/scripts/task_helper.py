#!/usr/bin/env python3
import os
import sys
import argparse
import re
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent

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
    
    # Template selection
    template_name = f"{task_type.upper()}.md"
    template_path = REPO_ROOT / ".agent" / "wiki-templates" / template_name
    
    if not template_path.exists():
        # Fallback to STORY.md if specific template doesn't exist
        template_path = REPO_ROOT / ".agent" / "wiki-templates" / "STORY.md"
    
    if not template_path.exists():
        template_content = f"# [{task_type.upper()}] {title}\n\n## Context\n\n## Impact\n\n## Acceptance Criteria\n"
    else:
        template_content = template_path.read_text(encoding='utf-8')
    
    # Replace placeholders
    content = template_content.replace("[STORY] Story Title", f"[{task_type.upper()}] {title}")
    content = content.replace("Story Title", title)
    if epic:
        content = content.replace("[epic name]", epic)
    
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
