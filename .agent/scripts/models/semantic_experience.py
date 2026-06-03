#!/usr/bin/env python3
"""Semantic Experience — Enhanced experience search using contextual grouping.
"""

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

import sys
import re
from pathlib import Path

try:
    from lib.paths import REPO_ROOT
except ImportError:
    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from lib.paths import REPO_ROOT

def search_semantic(query: str):
    lesson_files = []
    
    # 1. Global lessons file
    global_lessons = REPO_ROOT / ".agent" / "rules" / "LESSONS_LEARNED.md"
    if global_lessons.exists():
        lesson_files.append(global_lessons)
        
    # 2. Local decentralized lessons in skills
    skills_dir = REPO_ROOT / ".agent" / "skills"
    if skills_dir.exists():
        lesson_files.extend(skills_dir.rglob("LESSONS.md"))
        
    # 3. Archive lessons
    archive_dir = REPO_ROOT / "wiki" / "archive" / "experience"
    if archive_dir.exists():
        lesson_files.extend(archive_dir.glob("*.md"))

    if not lesson_files:
        return "No experience base found."

    entries = []
    for f_path in lesson_files:
        try:
            content = f_path.read_text(encoding="utf-8")
            # Split into entries (discarding anything before the first '### ')
            parts = re.split(r'\n### |^### ', content)
            for p in parts:
                cleaned = p.strip()
                if cleaned:
                    entries.append((f_path.name, cleaned))
        except Exception:
            continue

    results = []
    query_words = set(query.lower().split())
    
    for origin, entry in entries:
        title = entry.split('\n')[0]
        # Calculate overlap
        entry_words = set(entry.lower().replace('`', '').replace('|', '').split())
        overlap = len(query_words.intersection(entry_words))
        
        if overlap > 0:
            results.append((overlap, title, origin, entry))

    if not results:
        return f"No semantic matches for '{query}'."

    # Sort by overlap
    results.sort(key=lambda x: x[0], reverse=True)
    
    top = results[0]
    return f"🎯 Best Contextual Match (Score: {top[0]}, Source: {top[2]}):\n### {top[3]}"

if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(search_semantic(" ".join(sys.argv[1:])))
    else:
        print("Usage: semantic_experience.py <query>")
