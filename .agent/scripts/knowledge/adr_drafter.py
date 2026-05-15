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

# Configuration
ADR_DIR = Path("docs/adr")
WORKSPACE_ROOT = Path(".")

# Patterns that trigger ADR drafting
TRIGGERS = {
    "new_service": r"src/(services|handlers)/",
    "new_state_manager": r"src/(store|state|context)/",
    "new_dependency": r"(package\.json|go\.mod)",
    "ui_system_change": r"src/ui/components/shared/",
}

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

    # Draft ADR files
    drafted_files = []
    for i, dec in enumerate(potential_decisions):
        adr_id = f"{(len(list(ADR_DIR.glob('*.md'))) + 1 + i):04d}"
        filename = f"{adr_id}-{dec['title'].lower().replace(' ', '-')}.md"
        filepath = ADR_DIR / filename
        
        if not filepath.exists():
            content = f"""# ADR {adr_id}: {dec['title']}

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

    return {
        "status": "success",
        "drafted_adrs": drafted_files,
        "count": len(drafted_files)
    }

if __name__ == "__main__":
    result = draft_adr()
    print(json.dumps(result, indent=2))
