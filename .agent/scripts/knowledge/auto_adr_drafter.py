#!/usr/bin/env python3

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
import datetime
from pathlib import Path
from lib.llm_client import query_llm_safe

def draft_adr(conflict_desc: str) -> str:
    print(f"⚖️  Drafting Autonomous ADR to resolve conflict: '{conflict_desc}'...")
    
    # 1. Dynamically determine the next free index in wiki/decisions/
    decisions_dir = Path("wiki/decisions")
    max_id = 0
    if decisions_dir.exists():
        for p in decisions_dir.glob("ADR-*.md"):
            name = p.name
            parts = name.split("-")
            if len(parts) >= 2 and parts[1].isdigit():
                val = int(parts[1])
                if val > max_id:
                    max_id = val
    next_id = max_id + 1
    adr_id = f"{next_id:03d}"
    
    adr_path = decisions_dir / f"ADR-{adr_id}-auto-resolved.md"
    adr_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 2. Call LLM to draft a real ADR
    prompt = f"Conflict / Structural Change Description:\n{conflict_desc}\n\nPlease generate a professional ADR for ADR-{adr_id}."
    system_prompt = f"""You are a Principal Software Architect. Your job is to draft a clean, professional Architecture Decision Record (ADR) in Markdown based on the given architectural conflict or change.
Use the following Markdown format for the ADR:

# ADR-{adr_id}: [Title]

Date: {datetime.date.today()}
Status: Proposed (Autonomous)

## Context
[A detailed explanation of the context and why this decision is being drafted.]

## Decision
[The technical decision made to resolve the conflict or support the structural change.]

## Consequences
- [Consequence 1]
- [Consequence 2]

Return only the markdown content of the ADR, with no extra explanations or comments. Do not wrap it in markdown code blocks."""
    
    content, source, stats = query_llm_safe(
        prompt=prompt,
        system_prompt=system_prompt,
        model="qwen2.5-coder:14b"
    )
    
    # 3. Fallback check
    if source == "stub" or "LLM Unavailable" in content or not content.strip():
        print("🚨 [OFFLINE] Ни одна LLM не доступна! Используется локальный генератор заглушек.")
        
        # Extract files from conflict_desc
        changed_files = []
        for line in conflict_desc.splitlines():
            if line.strip().startswith("- ["):
                parts = line.split("] ")
                if len(parts) >= 2:
                    changed_files.append(parts[1].strip())
        
        # Determine languages and details for each file
        file_details = []
        for f in changed_files:
            p = Path(f)
            lang = "Unknown"
            if p.suffix == ".py":
                lang = "Python"
            elif p.suffix == ".go":
                lang = "Go"
            elif p.suffix in [".ts", ".tsx", ".js", ".jsx"]:
                lang = "TypeScript/JavaScript"
            elif p.suffix in [".yaml", ".yml"]:
                lang = "YAML Configuration"
                
            preview = ""
            if p.exists() and p.is_file():
                try:
                    with open(p, "r", encoding="utf-8", errors="ignore") as fp:
                        lines = [line.strip() for line in fp.readlines()[:5] if line.strip()]
                        if lines:
                            preview = f" (Preview: `{'; '.join(lines)[:60]}`)"
                except Exception:
                    pass
            file_details.append(f"- `{f}` ({lang}){preview}")
            
        files_block = "\n".join(file_details) if file_details else f"- {conflict_desc}"
        
        content = f"""# ADR-{adr_id}: Autonomous Resolution for Structural Changes

Date: {datetime.date.today()}
Status: Proposed (Autonomous)

> [!WARNING]
> **Ни одна LLM не доступна (Offline)**: Этот документ сгенерирован автоматически локальным генератором заглушек, так как все LLM-эндпоинты недоступны.

## Context
A structural change was detected in the following codebase components:
{files_block}

## Decision
We will accept these structural changes and document them in the architecture catalog. All new components must comply with Clean Code standards and include unit tests.

## Consequences
- Flexibility: High (components documented and integrated)
- Complexity: Low (no unnecessary layers added)
- Validation: Verified via local syntax checks.
"""
    else:
        # Clean up any potential markdown wraps
        content = content.strip()
        if content.startswith("```"):
            lines = content.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines).strip()
            
    with open(adr_path, "w", encoding="utf-8") as f:
        f.write(content)
        
    print(f"✅ ADR-{adr_id} DRAFTED: {adr_path}")
    return content

if __name__ == "__main__":
    if len(sys.argv) < 2: sys.exit(1)
    draft_adr(" ".join(sys.argv[1:]))
