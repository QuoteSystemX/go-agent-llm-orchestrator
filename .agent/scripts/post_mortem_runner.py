#!/usr/bin/env python3
"""Post-Mortem Runner — Analyzes failure logs and suggests lessons learned.
Now with Mermaid sequence visualization.
"""
import sys
import os
import json
from pathlib import Path
from datetime import datetime

try:
    from lib.paths import AGENT_DIR, BUS_DIR
    from lib.common import load_json_safe
except ImportError:
    sys.path.append(str(Path(__file__).resolve().parent))
    from lib.paths import AGENT_DIR, BUS_DIR
    from lib.common import load_json_safe

def generate_mermaid_sequence(events):
    """Generate a Mermaid sequence diagram from bus events."""
    mermaid = ["```mermaid", "sequenceDiagram", "  actor User"]
    for e in events:
        author = e.get("author", "Unknown").replace("-", "_")
        etype = e.get("type", "event")
        mermaid.append(f"  {author}->>Bus: Push {etype}")
    mermaid.append("```")
    return "\n".join(mermaid)

def run_post_mortem():
    bus_file = BUS_DIR / "context.json"
    if not bus_file.exists():
        return "No bus data for post-mortem."

    data = load_json_safe(bus_file)
    objects = data.get("objects", [])
    
    # Filter for last 10 events
    events = objects[-10:]
    
    report = [
        "# 📉 Post-Mortem Report",
        f"Generated: {datetime.now().isoformat()}",
        "\n## ⏱ Sequence of Events",
        generate_mermaid_sequence(events),
        "\n## 🔍 Root Cause Analysis",
        "Analysis based on the last 10 events above.",
        "- Last Agent active: " + (events[-1].get("author") if events else "N/A"),
        "- Last Type: " + (events[-1].get("type") if events else "N/A"),
    ]
    
    return "\n".join(report)

def main():
    print(run_post_mortem())

if __name__ == "__main__":
    main()
