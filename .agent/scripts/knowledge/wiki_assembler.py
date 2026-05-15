
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

import re
from pathlib import Path
import sys

"""Wiki Assembler - Modular Documentation Engine.

## Intuition (Mental Model)
The Assembler allows for context-aware documentation. By breaking the architecture 
into fragments, we can generate different views of the system (Hub vs. Spoke) 
without duplicating content or leaking sensitive application-specific details 
to downstream repositories.
"""

FRAGMENTS_BASE = Path("wiki/fragments")
LOCAL_APP_DIR = FRAGMENTS_BASE / "local"

def get_local_fragments() -> str:
    if not LOCAL_APP_DIR.exists():
        return ""
    
    fragments = sorted(list(LOCAL_APP_DIR.glob("*.md")))
    return "\n---\n".join(f.read_text() for f in fragments) if fragments else ""

def resolve_fragment(fragment_id: str, profile: str) -> str:
    if fragment_id == "SPOKE_LOCAL_APP":
        return get_local_fragments()

    if profile == "spoke" and fragment_id.startswith("app/"):
        return f"<!-- SKIPPED: {fragment_id} for spoke profile -->"
        
    path = FRAGMENTS_BASE / f"{fragment_id}.md"
    return path.read_text() if path.exists() else f"<!-- ERROR: Fragment missing: {fragment_id} -->"

def assemble_wiki(template_path: Path, output_path: Path, profile: str = "hub"):
    if not template_path.exists():
        return

    template = template_path.read_text()
    assembled = re.sub(
        r'<!--\s*@INJECT:(.*?)\s*-->', 
        lambda m: resolve_fragment(m.group(1).strip(), profile), 
        template
    )
    
    # Clean up redundant separators
    assembled = re.sub(r'\n---\n\s*<!-- SKIPPED:.*? -->\s*\n---\n', '\n---\n', assembled)
    assembled = re.sub(r'---\n\s*---\n', '---\n', assembled)

    output_path.write_text(assembled)
    print(f"✅ Wiki assembled: {output_path} ({profile})")

if __name__ == "__main__":
    profile = "spoke" if "--spoke" in sys.argv else "hub"
    assemble_wiki(Path("wiki/ARCHITECTURE.template.md"), Path("wiki/ARCHITECTURE.md"), profile)
