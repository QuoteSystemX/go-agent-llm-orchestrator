#!/usr/bin/env python3
"""Generate lightweight state snapshots from the Context Bus.
Collects high‑signal events (priority >= 5) and writes a concise markdown file
in `docs/snapshots/<timestamp>.md` for future reference.
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

import json
import os
from pathlib import Path
from datetime import datetime

def run_snapshot():
    BUS_DIR = Path('.agent/bus')
    SNAPSHOT_DIR = Path('docs/snapshots')
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    snapshot = {
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'events': []
    }

    if BUS_DIR.exists():
        for file in BUS_DIR.glob('*.json'):
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                # Consider only high‑signal events
                if data.get('priority', 0) >= 5:
                    summary = data.get('summary')
                    if not summary and isinstance(data.get('payload'), str):
                        summary = data.get('payload')[:200]
                    
                    snapshot['events'].append({
                        'id': file.name,
                        'type': data.get('type'),
                        'summary': summary,
                        'created_at': data.get('created_at')
                    })
            except Exception:
                continue

    # Write markdown snapshot
    filename = SNAPSHOT_DIR / f"snapshot-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.md"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(f"# State Snapshot – {snapshot['timestamp']}\n\n")
        for ev in snapshot['events']:
            summary = ev.get('summary') or ""
            f.write(f"- **{ev['id']}** – {ev['type']} – {summary[:120]}\n")

    return {
        'status': 'completed',
        'snapshot_file': str(filename),
        'event_count': len(snapshot['events'])
    }

if __name__ == "__main__":
    print(json.dumps(run_snapshot(), indent=2))
