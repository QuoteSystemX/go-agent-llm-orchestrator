#!/usr/bin/env python3
"""ADR Observer - Reactive Wiki Auto-Publisher for Council of Sages.

## Intuition (Mental Model)
The ADR Observer watches the Context Bus for approved architectural verdicts.
When a decision is approved, it reactively parses the complete debate log
(either structured critiques/resolutions or multi-role strategic opinions),
compiles it into a premium ADR Markdown document, and rebuilds the Wiki manifest.
"""

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT, BUS_DIR, RULES_DIR
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
from datetime import datetime

try:
    from lib.paths import REPO_ROOT, BUS_DIR
    from lib.common import load_json_safe
except ImportError:
    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from lib.paths import REPO_ROOT, BUS_DIR
    from lib.common import load_json_safe

BUS_FILE = BUS_DIR / "context.json"
DECISIONS_DIR = REPO_ROOT / "wiki" / "decisions"
TEMPLATES_DIR = REPO_ROOT / ".agent" / "wiki-templates"
WIKI_DIR = REPO_ROOT / "wiki"

def _find_next_num() -> int:
    """Scan wiki/decisions/ for existing ADRs and return the next free index."""
    DECISIONS_DIR.mkdir(parents=True, exist_ok=True)
    existing = list(DECISIONS_DIR.glob("ADR-*.md"))
    next_num = 1
    if existing:
        nums = []
        for f in existing:
            match = re.search(r'ADR-(\d+)', f.name)
            if match:
                nums.append(int(match.group(1)))
        if nums:
            next_num = max(nums) + 1
    return next_num

def _adr_already_exists(plan_id: str) -> bool:
    """Scan existing decisions to check if this plan_id is already published."""
    if not DECISIONS_DIR.exists():
        return False
    for f in DECISIONS_DIR.glob("ADR-*.md"):
        try:
            content = f.read_text(encoding="utf-8")
            # Match metadata or references
            if f"plan_ref: {plan_id}" in content or f"plan_ref: '{plan_id}'" in content:
                return True
        except Exception:
            pass
    return False

def compile_expert_debate_log(critiques: dict, resolutions: dict) -> str:
    """Format CritiqueList and VerdictList into a structured debate Markdown table."""
    lines = []
    lines.append("## Debate Log")
    lines.append("")
    lines.append("The expert panel conducted a multi-turn critique and defense session:")
    lines.append("")
    lines.append("| Critique ID | Severity & Category | Critique / Risk Point | Proposer Defense & Resolution | Accepted |")
    lines.append("| :--- | :--- | :--- | :--- | :--- |")

    crits = critiques.get("critiques", []) if isinstance(critiques, dict) else []
    resols = resolutions.get("resolutions", []) if isinstance(resolutions, dict) else []

    resolutions_map = {r.get("critique_id"): r for r in resols}

    for c in crits:
        c_id = c.get("id", "N/A")
        cat = c.get("category", "general")
        sev = c.get("severity", "warning")
        desc = c.get("description", "").replace("\n", " ")
        
        res = resolutions_map.get(c_id)
        res_text = "No resolution provided."
        accepted_icon = "❌ No"
        if res:
            res_text = res.get("resolution", "").replace("\n", " ")
            accepted_icon = "✅ Yes" if res.get("accepted") else "❌ No"
            
        lines.append(f"| {c_id} | `{sev}` ({cat}) | {desc} | {res_text} | {accepted_icon} |")
        
    return "\n".join(lines)

def compile_strategic_debate_log(responses: dict) -> str:
    """Format 4-role strategic opinions into a debate timeline."""
    lines = []
    lines.append("## Strategic Debate Transcript")
    lines.append("")
    lines.append("The hidden war-room simulation debated the topic with different cognitive perspectives:")
    lines.append("")
    
    if "optimist" in responses:
        lines.append("### 🎭 **OPTIMIST** (Architect/Advocate)")
        lines.append(f"> {responses['optimist'].strip()}")
        lines.append("")
    if "skeptic" in responses:
        lines.append("### 🕵️ **SKEPTIC** (Cynical Engineer/SRE)")
        lines.append(f"> {responses['skeptic'].strip()}")
        lines.append("")
    if "user_advocate" in responses:
        lines.append("### 👤 **USER ADVOCATE** (UX/DNA Sync)")
        lines.append(f"> {responses['user_advocate'].strip()}")
        lines.append("")
        
    return "\n".join(lines)

def process_bus_events() -> bool:
    """Scan Context Bus, find new approved verdicts, and auto-publish them."""
    if not BUS_FILE.exists():
        print("🚌 Bus is empty (context.json missing).")
        return False

    bus_data = load_json_safe(BUS_FILE)
    if not bus_data or "objects" not in bus_data:
        return False

    # Filter all verification results
    verdicts = [obj for obj in bus_data["objects"] if obj.get("type") == "verification_result"]
    if not verdicts:
        return False

    published_any = False

    for obj in verdicts:
        content = obj.get("content", {})
        if not content:
            continue

        plan_id = content.get("plan_id")
        title = content.get("title", "Architectural Decision")
        verdict = content.get("verdict", {})
        author = obj.get("author", "arbitrator")
        date_str = datetime.now().strftime("%Y-%m-%d")

        if not plan_id or verdict.get("status") != "approved":
            continue

        # Check if already processed
        if _adr_already_exists(plan_id):
            continue

        print(f"🌟 Reacting to approved verdict on Context Bus: '{plan_id}'...")

        next_num = _find_next_num()
        filename = f"ADR-{next_num:03d}-{plan_id.lower().replace('_', '-').replace(' ', '-')}.md"
        path = DECISIONS_DIR / filename

        # Compile transcript section
        debate_log = ""
        debate_type = content.get("debate_type", "expert")
        if debate_type == "expert":
            debate_log = compile_expert_debate_log(content.get("critiques", {}), content.get("resolutions", {}))
        elif debate_type == "strategic":
            debate_log = compile_strategic_debate_log(content.get("responses", {}))

        # Render complete ADR file
        consequences = []
        if verdict.get("conditions"):
            consequences.append("### Conditions for Approval")
            for c in verdict["conditions"]:
                consequences.append(f"- [ ] {c}")
            consequences.append("")
        if verdict.get("risk_areas"):
            consequences.append("### Identified Risk Areas")
            for r in verdict["risk_areas"]:
                consequences.append(f"- `WARNING`: {r}")
            consequences.append("")
        
        consequences_str = "\n".join(consequences) if consequences else "- [x] Decision successfully ratified and synced."

        yaml_title = title.replace('"', '\\"')
        adr_body = f"""---
title: "ADR-{next_num:03d}: {yaml_title}"
tags:
  - project
status: approved
plan_ref: {plan_id}
---

# ADR-{next_num:03d}: {title}

**Status**: APPROVED (confidence: {verdict.get('confidence', 1.0):.2f})
**Date**: {date_str}
**Author**: `{author}`

## Context
{content.get('context', content.get('plan_text', 'Architectural proposal context loaded from Context Bus.'))}

## Decision
{verdict.get('summary', 'The Council of Sages successfully completed consensus and approved the proposal.')}

## Consequences
{consequences_str}

{debate_log}
"""

        path.write_text(adr_body, encoding="utf-8")
        print(f"📝 Published new ADR to: {path}")

        # Trigger Wiki Re-assembly and Link Synchronization
        _trigger_wiki_sync()
        published_any = True

        # Clickable absolute path printed in terminal
        absolute_uri = f"file://{path.resolve()}"
        print(f"🔗 Published ADR Link: \033[94m\033[4m{absolute_uri}\033[0m")

    return published_any

def _trigger_wiki_sync():
    """Trigger wiki_sync.py to auto-link the new decisions and compile ARCHITECTURE.md."""
    try:
        from knowledge import wiki_sync
        wiki_sync.sync_wiki()
    except ImportError:
        # Fallback to subprocess call
        import subprocess
        sync_script = REPO_ROOT / ".agent" / "scripts" / "knowledge" / "wiki_sync.py"
        if sync_script.exists():
            subprocess.run([sys.executable, str(sync_script)], capture_output=True)

if __name__ == "__main__":
    process_bus_events()
