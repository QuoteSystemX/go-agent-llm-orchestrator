#!/usr/bin/env python3
import sys
import datetime
from pathlib import Path

def draft_adr(conflict_desc: str):
    print(f"⚖️  Drafting Autonomous ADR to resolve conflict: '{conflict_desc}'...")
    
    adr_id = "022" # Simulated next ID
    adr_path = Path(f"wiki/decisions/ADR-{adr_id}-auto-resolved.md")
    adr_path.parent.mkdir(parents=True, exist_ok=True)
    
    content = f"""# ADR-{adr_id}: Autonomous Resolution for '{conflict_desc}'

Date: {datetime.date.today()}
Status: Proposed (Autonomous)

## Context
A conflict was detected by the Intelligent Gateway during intent validation.

## Decision
We will adapt the architecture to support the requested intent by implementing a bridge/adapter pattern.

## Consequences
- Flexibility: High
- Complexity: Medium
- Maintenance: Handled by Autonomous Maintainer.
"""
    
    with open(adr_path, "w") as f:
        f.write(content)
        
    print(f"✅ ADR-{adr_id} DRAFTED: {adr_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2: sys.exit(1)
    draft_adr(" ".join(sys.argv[1:]))
