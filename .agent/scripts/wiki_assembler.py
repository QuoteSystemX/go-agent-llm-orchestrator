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

def assemble_wiki(template_path, output_path, profile="hub"):
    """
    Assembles a markdown file from a template by injecting fragments.
    
    Tags: <!-- @INJECT:path/to/fragment -->
    """
    if not template_path.exists():
        print(f"Template not found: {template_path}")
        return

    content = template_path.read_text()
    
    def inject_fragment(match):
        fragment_rel_path = match.group(1)
        
        # Handle Auto-Discovery for Spoke Local App fragments
        if fragment_rel_path == "SPOKE_LOCAL_APP":
            local_dir = Path("wiki/fragments/local")
            if local_dir.exists():
                local_fragments = sorted(list(local_dir.glob("*.md")))
                if local_fragments:
                    return "\n---\n".join([f.read_text() for f in local_fragments])
            return "" # Nothing to inject

        # Provisioning Logic: Skip app fragments if profile is 'spoke'
        if profile == "spoke" and fragment_rel_path.startswith("app/"):
            return f"<!-- SKIPPED: {fragment_rel_path} for spoke profile -->"
            
        fragment_path = Path("wiki/fragments") / f"{fragment_rel_path}.md"
        
        if fragment_path.exists():
            return fragment_path.read_text()
        else:
            return f"<!-- ERROR: Fragment not found at {fragment_path} -->"

    # Replace injection tags
    assembled_content = re.sub(r'<!-- @INJECT:(.*?) -->', inject_fragment, content)
    
    # Cleanup: Remove doubled separators and empty sections
    assembled_content = re.sub(r'\n---\n\s*<!-- SKIPPED:.*? -->\s*\n---\n', '\n---\n', assembled_content)
    assembled_content = re.sub(r'---\n\s*---\n', '---\n', assembled_content)

    output_path.write_text(assembled_content)
    print(f"✅ Wiki assembled to {output_path} (Profile: {profile})")

if __name__ == "__main__":
    profile_arg = "hub"
    if len(sys.argv) > 1 and sys.argv[1] == "--spoke":
        profile_arg = "spoke"
        
    template = Path("wiki/ARCHITECTURE.template.md")
    output = Path("wiki/ARCHITECTURE.md")
    
    assemble_wiki(template, output, profile=profile_arg)
