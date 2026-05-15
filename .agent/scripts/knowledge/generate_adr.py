#!/usr/bin/env python3
"""ADR Generator — Creates Architectural Decision Records from logs or text.
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
from datetime import datetime

try:
    from lib.paths import REPO_ROOT
except ImportError:
    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from lib.paths import REPO_ROOT

ADR_DIR = REPO_ROOT / "wiki" / "decisions"

def generate_adr(title: str, context: str, decision: str):
    """Generate an ADR file based on the template."""
    ADR_DIR.mkdir(parents=True, exist_ok=True)
    
    # Find next number
    existing = list(ADR_DIR.glob("ADR-*.md"))
    next_num = 1
    if existing:
        nums = [int(re.search(r'ADR-(\d+)', f.name).group(1)) for f in existing if re.search(r'ADR-(\d+)', f.name)]
        if nums: next_num = max(nums) + 1
    
    filename = f"ADR-{next_num:03d}-{title.lower().replace(' ', '-')}.md"
    path = ADR_DIR / filename
    
    content = f"""# ADR-{next_num:03d}: {title}

**Date**: {datetime.now().strftime("%Y-%m-%d")}
**Status**: PROPOSED

## Context
{context}

## Decision
{decision}

## Consequences
- [ ] Documentation updated
- [ ] Team notified
- [ ] Implementation completed
"""
    
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    
    return f"✅ ADR created: {path}"

def main():
    if len(sys.argv) < 4:
        print("Usage: generate_adr.py <title> <context> <decision>")
        sys.exit(1)
    
    print(generate_adr(sys.argv[1], sys.argv[2], sys.argv[3]))

if __name__ == "__main__":
    main()
