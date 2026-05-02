#!/usr/bin/env python3
"""Semantic Experience — Enhanced experience search using contextual grouping.
"""
import sys
import re
from pathlib import Path

try:
    from lib.paths import REPO_ROOT
except ImportError:
    sys.path.append(str(Path(__file__).resolve().parent))
    from lib.paths import REPO_ROOT

def search_semantic(query: str):
    lessons_file = REPO_ROOT / "wiki" / "LESSONS_LEARNED.md"
    if not lessons_file.exists():
        return "No experience base found."

    content = lessons_file.read_text(encoding="utf-8")
    
    # Split into entries
    entries = re.split(r'### ', content)[1:]
    
    results = []
    query_words = set(query.lower().split())
    
    for entry in entries:
        title = entry.split('\n')[0]
        # Calculate overlap
        entry_words = set(entry.lower().replace('`', '').replace('|', '').split())
        overlap = len(query_words.intersection(entry_words))
        
        if overlap > 0:
            results.append((overlap, title, entry))

    if not results:
        return f"No semantic matches for '{query}'."

    # Sort by overlap
    results.sort(key=lambda x: x[0], reverse=True)
    
    top = results[0]
    return f"🎯 Best Contextual Match (Score: {top[0]}):\n### {top[1]}\n{top[2]}"

if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(search_semantic(" ".join(sys.argv[1:])))
    else:
        print("Usage: semantic_experience.py <query>")
