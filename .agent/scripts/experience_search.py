#!/usr/bin/env python3
"""Experience Search – query historical Lessons Learned.
Usage: python3 experience_search.py "keyword"
Searches through `docs/snapshots/` markdown files and ADRs for matching topics.
Returns a concise JSON list of matching entries.
"""
import sys
import json
import re
from pathlib import Path

if len(sys.argv) < 2:
    print(json.dumps({"error": "Missing search term"}, indent=2))
    sys.exit(1)

term = sys.argv[1].lower()
results = []

# Search snapshots
snap_dir = Path('docs/snapshots')
for file in snap_dir.glob('*.md'):
    try:
        text = file.read_text(encoding='utf-8').lower()
        if term in text:
            # capture first matching line
            match = re.search(r"-\s+\*\*(.+?)\*\*.*" + re.escape(term), text, re.IGNORECASE)
            snippet = match.group(0) if match else "..."
            results.append({"type": "snapshot", "file": str(file), "snippet": snippet.strip()})
    except Exception:
        continue

# Search ADRs
adr_dir = Path('docs/adr')
for adr in adr_dir.glob('*.md'):
    try:
        txt = adr.read_text(encoding='utf-8').lower()
        if term in txt:
            header = adr.stem.replace('-', ' ')
            results.append({"type": "adr", "file": str(adr), "title": header})
    except Exception:
        continue

print(json.dumps({"term": term, "matches": results}, indent=2))
