#!/usr/bin/env python3
"""ADR Drafter - Automated Architectural Decision Record Generation.
Scans the workspace for structural changes and drafts ADRs for the Archivist.
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

import os
import json
import re
from pathlib import Path
from datetime import datetime

try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]

# Configuration
ADR_DIR = REPO_ROOT / "wiki" / "decisions"
WORKSPACE_ROOT = Path(".")

# Patterns that trigger ADR drafting
TRIGGERS = {
    "new_service": r"src/(services|handlers)/",
    "new_state_manager": r"src/(store|state|context)/",
    "new_dependency": r"(package\.json|go\.mod)",
    "ui_system_change": r"src/ui/components/shared/",
}

def next_adr_id() -> int:
    """Max existing ADR-NNN id + 1. Counting files undercounts after deletions/renumbering
    (see .agent/skills/architecture/scripts/generate_adr.py's identical helper — reused pattern,
    not reimplemented from scratch)."""
    max_id = 0
    for f in ADR_DIR.glob("ADR-*.md"):
        match = re.match(r"ADR-(\d+)-", f.name)
        if match:
            max_id = max(max_id, int(match.group(1)))
    return max_id + 1


def draft_adr():
    if not ADR_DIR.exists():
        ADR_DIR.mkdir(parents=True, exist_ok=True)

    # In a real scenario, this would use `git diff` to find recent changes.
    # For now, we scan for "significant" files to see if they lack documentation.
    
    potential_decisions = []
    
    # 1. Check for new shared components (UI System)
    shared_ui = list(WORKSPACE_ROOT.glob("paperclip-plugin/src/ui/components/shared/*.tsx"))
    if shared_ui:
        potential_decisions.append({
            "title": "Standardization of UI Component System",
            "context": f"Detected {len(shared_ui)} shared components. Standardizing on a premium design system.",
            "consequences": "Improved consistency, but requires adherence to BaseUI patterns."
        })

    # 2. Check for Go handlers (API Patterns)
    go_handlers = list(WORKSPACE_ROOT.glob(".agent/mcp-server-agent-kit/*.go"))
    if go_handlers:
        potential_decisions.append({
            "title": "Adoption of MCP Go Server Framework",
            "context": "Implemented a modular Go-based MCP server for agent orchestration.",
            "consequences": "High performance, but requires Go expertise for handler expansion."
        })

    # Draft ADR files. `next_id` advances locally across the loop rather than being
    # re-derived from a mutating directory count per iteration (the bug that made IDs climb
    # unpredictably and re-glob a directory this same loop was writing into).
    drafted_files = []
    next_id = next_adr_id()
    existing_slugs = set()
    for f in ADR_DIR.glob("ADR-*.md"):
        m = re.match(r"ADR-\d+-(.+)\.md$", f.name)
        if m:
            existing_slugs.add(m.group(1))

    for dec in potential_decisions:
        slug = dec['title'].lower().replace(' ', '-')

        # Skip if an ADR for this exact decision already exists under ANY id — not just an
        # exact-filename check against the current id, which never matches (the id always
        # increments) and let this trigger re-draft the same two decisions indefinitely. Exact
        # match on the slug portion, not substring containment — `slug in f.name` would also
        # match e.g. an unrelated "ADR-005-re-adoption-of-mcp-go-server-framework-v2.md".
        if slug in existing_slugs:
            continue

        adr_id = f"{next_id:03d}"
        filename = f"ADR-{adr_id}-{slug}.md"
        filepath = ADR_DIR / filename

        content = f"""# ADR-{adr_id}: {dec['title']}

## Status
DRAFT (Proposed by Archivist)

## Intuition (Mental Model)
*Prose-first explanation of why this decision is being made and the intuition behind the architecture.*

## Context
{dec['context']}

## Decision
[Archivist recommendation based on detected patterns]

## Consequences
{dec['consequences']}

## Metadata
- **Detected At**: {datetime.now().isoformat()}
- **Suggested By**: Archivist Agent
"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        drafted_files.append(str(filepath))
        next_id += 1

    return {
        "status": "success",
        "drafted_adrs": drafted_files,
        "count": len(drafted_files)
    }

if __name__ == "__main__":
    result = draft_adr()
    print(json.dumps(result, indent=2))
