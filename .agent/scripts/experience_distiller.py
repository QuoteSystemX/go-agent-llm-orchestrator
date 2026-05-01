#!/usr/bin/env python3
"""Experience Distiller — Lesson archiving, skill-tagging, and per-skill filtering.

Manages the lifecycle of LESSONS_LEARNED.md entries:
  - Archives lessons older than 30 days to wiki/archive/experience/
  - Supports skill-tagged entries for contextual loading
  - Filters lessons by skill tag for agent skill-loading

Usage:
    python3 experience_distiller.py              # distill (archive old lessons)
    python3 experience_distiller.py --skill go-patterns   # filter by skill tag
    python3 experience_distiller.py --list-skills         # list all skill tags found

Entry format:
    ### [YYYY-MM-DD] [TAG] [skill-name] Title
    Description of the lesson learned.

    ### [2026-04-28] [BUG] [go-patterns] xsync MapOf nil pointer on empty init
    Always initialize xsync.MapOf with NewMapOf(), never with zero-value.
"""
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
LESSONS_PATH = REPO_ROOT / ".agent" / "rules" / "LESSONS_LEARNED.md"
ARCHIVE_DIR = REPO_ROOT / "wiki" / "archive" / "experience"

# Retention policy: lessons older than this are archived
RETENTION_DAYS = 30


def parse_entries(content: str) -> tuple[str, list[str]]:
    """Split LESSONS_LEARNED.md into header and individual entries."""
    entries = re.split(r'\n### ', content)
    header = entries[0]
    lessons = entries[1:]
    return header, lessons


def extract_date(entry: str) -> datetime | None:
    """Extract date from [YYYY-MM-DD] in an entry."""
    date_match = re.search(r'\[(\d{4}-\d{2}-\d{2})\]', entry)
    if date_match:
        try:
            return datetime.strptime(date_match.group(1), '%Y-%m-%d')
        except ValueError:
            return None
    return None


def extract_skill_tag(entry: str) -> str | None:
    """Extract skill tag from entry.

    Looks for the pattern: [DATE] [TAG] [skill-name]
    where skill-name is a lowercase-with-dashes identifier.
    """
    match = re.search(r'\]\s*\[\w+\]\s*\[([\w-]+)\]', entry)
    return match.group(1) if match else None


def distill_lessons() -> str:
    """Archive lessons older than RETENTION_DAYS."""
    if not LESSONS_PATH.exists():
        return "No lessons file found."

    with open(LESSONS_PATH, 'r') as f:
        content = f.read()

    header, lessons = parse_entries(content)

    active_lessons = []
    archived_count = 0
    threshold = datetime.now() - timedelta(days=RETENTION_DAYS)

    if not ARCHIVE_DIR.exists():
        ARCHIVE_DIR.mkdir(parents=True)

    for lesson in lessons:
        lesson_date = extract_date(lesson)
        if lesson_date and lesson_date < threshold:
            archive_file = ARCHIVE_DIR / f"{lesson_date.strftime('%Y-%m-%d')}.md"
            with open(archive_file, 'a') as af:
                af.write(f"### {lesson}\n")
            archived_count += 1
            continue

        active_lessons.append(f"### {lesson}")

    with open(LESSONS_PATH, 'w') as f:
        f.write(header)
        if active_lessons:
            f.write("\n" + "\n".join(active_lessons))

    return f"Distillation complete: {len(active_lessons)} active, {archived_count} archived."


def filter_by_skill(skill_name: str) -> str:
    """Return only lessons tagged with a specific skill.

    When an agent loads a skill (e.g. go-patterns), it can call this
    to get project-specific warnings relevant to that domain.
    """
    if not LESSONS_PATH.exists():
        return ""

    with open(LESSONS_PATH, 'r') as f:
        content = f.read()

    _, lessons = parse_entries(content)

    matched = []
    for lesson in lessons:
        tag = extract_skill_tag(lesson)
        if tag and tag == skill_name:
            matched.append(f"### {lesson}")

    if not matched:
        return f"No lessons found for skill '{skill_name}'."

    return f"Found {len(matched)} lesson(s) for '{skill_name}':\n\n" + "\n".join(matched)


def list_skill_tags() -> str:
    """List all unique skill tags found in LESSONS_LEARNED.md."""
    if not LESSONS_PATH.exists():
        return "No lessons file found."

    with open(LESSONS_PATH, 'r') as f:
        content = f.read()

    _, lessons = parse_entries(content)

    tags = set()
    for lesson in lessons:
        tag = extract_skill_tag(lesson)
        if tag:
            tags.add(tag)

    if not tags:
        return "No skill-tagged lessons found. Use format: ### [DATE] [TAG] [skill-name] Title"

    sorted_tags = sorted(tags)
    return f"Skill tags ({len(sorted_tags)}): " + ", ".join(sorted_tags)


def main():
    if "--skill" in sys.argv:
        idx = sys.argv.index("--skill")
        if idx + 1 < len(sys.argv):
            print(filter_by_skill(sys.argv[idx + 1]))
        else:
            print("Usage: experience_distiller.py --skill <skill-name>")
            sys.exit(1)
    elif "--list-skills" in sys.argv:
        print(list_skill_tags())
    else:
        print(distill_lessons())


if __name__ == "__main__":
    main()
