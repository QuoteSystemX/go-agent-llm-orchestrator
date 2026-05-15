#!/usr/bin/env python3
"""Experience Search – query historical Lessons Learned.
Usage: python3 experience_search.py "keyword"
Searches through `docs/snapshots/` markdown files and ADRs for matching topics.
Returns a concise JSON list of matching entries.
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
import json
import re
from pathlib import Path

def search_experience(term):
    results = []
    term = term.lower()

    # Search snapshots
    snap_dir = Path('docs/snapshots')
    if snap_dir.exists():
        for file in snap_dir.glob('*.md'):
            try:
                text = file.read_text(encoding='utf-8')
                text_lower = text.lower()
                if term in text_lower:
                    # capture first matching line
                    # We use re.IGNORECASE, so we match against original text for snippet
                    match = re.search(r"-\s+\*\*(.+?)\*\*.*" + re.escape(term), text, re.IGNORECASE)
                    snippet = match.group(0) if match else "..."
                    results.append({"type": "snapshot", "file": str(file), "snippet": snippet.strip()})
            except Exception:
                continue

    # Search ADRs
    adr_dir = Path('docs/adr')
    if adr_dir.exists():
        for adr in adr_dir.glob('*.md'):
            try:
                txt = adr.read_text(encoding='utf-8').lower()
                if term in txt:
                    header = adr.stem.replace('-', ' ')
                    results.append({"type": "adr", "file": str(adr), "title": header})
            except Exception:
                continue

    return {"term": term, "matches": results}

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Missing search term"}, indent=2))
        sys.exit(1)
    
    term = sys.argv[1]
    res = search_experience(term)
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    main()
