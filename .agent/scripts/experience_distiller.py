#!/usr/bin/env python3
"""Experience Distiller — Lesson archiving, skill-tagging, and per-skill filtering.
"""
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

def detect_project_language() -> str:
    """Detect the dominant programming language of the project."""
    from lib.paths import REPO_ROOT
    exts = [f.suffix for f in REPO_ROOT.glob("**/*") if f.is_file()]
    counts = {".go": exts.count(".go"), ".py": exts.count(".py"), ".js": exts.count(".js"), ".ts": exts.count(".ts")}
    dominant = max(counts, key=counts.get)
    mapping = {".go": "Go", ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript"}
    return mapping.get(dominant, "Unknown")

# Import from common lib
try:
    from lib.paths import LESSONS_PATH, GLOBAL_LESSONS_PATH, AGENT_DIR, REPO_ROOT
    from lib.common import load_json_safe
    import semantic_brain_engine
except ImportError:
    sys.path.append(str(Path(__file__).resolve().parent))
    from lib.paths import LESSONS_PATH, GLOBAL_LESSONS_PATH, AGENT_DIR, REPO_ROOT
    from lib.common import load_json_safe
    import semantic_brain_engine

ARCHIVE_DIR = REPO_ROOT / "wiki" / "archive" / "experience"
RETENTION_DAYS = 30

def parse_entries(content: str) -> tuple[str, list[str]]:
    """Split content into header and individual entries."""
    if content.startswith("### "):
        # No header, or header is empty
        header = ""
        # We need to split by \n### but the first one is at the start
        # Add a newline at start to make split uniform
        lessons_content = "\n" + content
    else:
        # Split normally
        lessons_content = content

    parts = re.split(r'\n### ', lessons_content)
    header = parts[0] if not content.startswith("### ") else ""
    lessons = parts[1:]
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
    """Extract skill tag from entry."""
    match = re.search(r'\]\s*\[\w+\]\s*\[([\w-]+)\]', entry)
    return match.group(1) if match else None

def distill_lessons() -> str:
    """Archive lessons older than RETENTION_DAYS."""
    if not LESSONS_PATH.exists():
        return "No lessons file found."

    with open(LESSONS_PATH, 'r', encoding="utf-8") as f:
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
            with open(archive_file, 'a', encoding="utf-8") as af:
                af.write(f"### {lesson}\n")
            archived_count += 1
            continue

        active_lessons.append(f"### {lesson}")

    with open(LESSONS_PATH, 'w', encoding="utf-8") as f:
        f.write(header)
        if active_lessons:
            f.write("\n" + "\n".join(active_lessons))

    return f"Distillation complete: {len(active_lessons)} active, {archived_count} archived."

def filter_by_skill(skill_name: str) -> str:
    """Return lessons tagged with a specific skill, including archives."""
    all_lessons = []
    
    # 1. Active lessons
    if LESSONS_PATH.exists():
        with open(LESSONS_PATH, 'r', encoding="utf-8") as f:
            _, active = parse_entries(f.read())
            all_lessons.extend(active)
            
    # 2. Archived lessons
    if ARCHIVE_DIR.exists():
        for archive_file in ARCHIVE_DIR.glob("*.md"):
            with open(archive_file, 'r', encoding="utf-8") as f:
                content = f.read()
                if not content.startswith("### "): content = "\n### " + content
                _, archived = parse_entries(content)
                all_lessons.extend(archived)
                
    # 3. Global lessons
    if GLOBAL_LESSONS_PATH.exists():
        with open(GLOBAL_LESSONS_PATH, 'r', encoding="utf-8") as f:
            content = f.read()
            if not content.startswith("### "): content = "\n### " + content
            _, global_l = parse_entries(content)
            all_lessons.extend(global_l)

    matched = []
    for lesson in all_lessons:
        tag = extract_skill_tag(lesson)
        if tag and tag == skill_name:
            matched.append(f"### {lesson}")

    if not matched:
        return f"No lessons found for skill '{skill_name}'."

    return f"Found {len(matched)} lesson(s) for '{skill_name}' (including archives):\n\n" + "\n".join(matched)

def search_lessons(query: str) -> str:
    """Find lessons using hybrid semantic search (Global + Local)."""
    # 1. Global Search (Semantic)
    semantic_results = semantic_brain_engine.search_lessons(query, top_n=3)
    
    # 2. Local Search (Traditional Fallback for active lessons)
    all_local = []
    if LESSONS_PATH.exists():
        with open(LESSONS_PATH, 'r', encoding="utf-8") as f:
            _, active = parse_entries(f.read())
            all_local.extend(active)
            
    query_terms = set(query.lower().split())
    local_matches = []
    for lesson in all_local:
        lesson_lower = lesson.lower()
        score = sum(2 if term in lesson_lower else 0 for term in query_terms)
        if score > 0:
            local_matches.append((score, lesson))
            
    # Combine results
    output = [f"🧠 Semantic Matches (Global Brain):"]
    if semantic_results:
        for res in semantic_results:
            output.append(f"### {res['content']} (Score: {res['score']:.2f})")
    else:
        output.append("_No semantic matches found._")
        
    if local_matches:
        local_matches.sort(key=lambda x: x[0], reverse=True)
        output.append(f"\n📂 Local Matches:")
        for r in local_matches[:3]:
            output.append(f"### {r[1]}")
            
    return "\n".join(output)

def list_skill_tags() -> str:
    """List all unique skill tags found."""
    tags = set()
    
    # Check active, archives, and global
    files_to_check = [LESSONS_PATH, GLOBAL_LESSONS_PATH]
    if ARCHIVE_DIR.exists():
        files_to_check.extend(ARCHIVE_DIR.glob("*.md"))
        
    for path in files_to_check:
        if path.exists():
            with open(path, 'r', encoding="utf-8") as f:
                content = f.read()
                if not content.startswith("### ") and path != LESSONS_PATH:
                    content = "\n### " + content
                _, lessons = parse_entries(content)
                for lesson in lessons:
                    tag = extract_skill_tag(lesson)
                    if tag:
                        tags.add(tag)

    if not tags:
        return "No skill-tagged lessons found."

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
    elif "--query" in sys.argv:
        idx = sys.argv.index("--query")
        if idx + 1 < len(sys.argv):
            print(search_lessons(sys.argv[idx + 1]))
        else:
            print("Usage: experience_distiller.py --query <search-text>")
            sys.exit(1)
    elif "--list-skills" in sys.argv:
        print(list_skill_tags())
    else:
        print(distill_lessons())

if __name__ == "__main__":
    main()
