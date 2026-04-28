#!/usr/bin/env python3
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
LESSONS_PATH = REPO_ROOT / ".agent" / "rules" / "LESSONS_LEARNED.md"
ARCHIVE_DIR = REPO_ROOT / "wiki" / "archive" / "experience"

def distill_lessons():
    if not LESSONS_PATH.exists():
        return "No lessons file found."

    with open(LESSONS_PATH, 'r') as f:
        content = f.read()

    # Simple logic: Extract entries and check dates
    # Entries should be formatted as: ### [DATE] [TAG] Title
    entries = re.split(r'\n### ', content)
    header = entries[0]
    lessons = entries[1:]

    active_lessons = []
    archived_count = 0
    
    # Retention policy: 30 days
    threshold = datetime.now() - timedelta(days=30)

    if not ARCHIVE_DIR.exists():
        ARCHIVE_DIR.mkdir(parents=True)

    for lesson in lessons:
        # Extract date from [YYYY-MM-DD]
        date_match = re.search(r'\[(\d{4}-\d{2}-\d{2})\]', lesson)
        if date_match:
            lesson_date = datetime.strptime(date_match.group(1), '%Y-%m-%d')
            if lesson_date < threshold:
                # Archive it
                archive_file = ARCHIVE_DIR / f"{date_match.group(1)}.md"
                with open(archive_file, 'a') as af:
                    af.write(f"### {lesson}\n")
                archived_count += 1
                continue
        
        active_lessons.append(f"### {lesson}")

    # Write back active lessons
    with open(LESSONS_PATH, 'w') as f:
        f.write(header)
        if active_lessons:
            f.write("\n" + "\n".join(active_lessons))

    return f"Distillation complete: {len(active_lessons)} active, {archived_count} archived."

if __name__ == "__main__":
    print(distill_lessons())
