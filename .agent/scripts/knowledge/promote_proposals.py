#!/usr/bin/env python3
import os
import shutil
from pathlib import Path

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    import sys
    REPO_ROOT = Path(__file__).resolve().parents[3]
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))

def promote_active_proposals():
    """Promotes active proposals to the decisions knowledge base."""
    print("🚀 Bridge Team: Promoting Knowledge Proposals...")
    
    source_dir = REPO_ROOT / "docs" / "proposals"
    target_dir = REPO_ROOT / ".agent" / "knowledge" / "decisions"
    
    if not source_dir.exists():
        print(f"⚠️ Source directory {source_dir} not found. Skipping.")
        return
        
    os.makedirs(target_dir, exist_ok=True)
    
    promoted_count = 0
    for item in source_dir.glob("PROPOSAL-*.md"):
        content = item.read_text()
        
        # Only promote if it's "Active" or "Approved"
        if "Status: Active" in content or "Status: Approved" in content:
            target_path = target_dir / item.name
            
            print(f"✅ Promoting {item.name} to knowledge base.")
            
            # Remove the "PROPOSAL" tag from headers if present
            content = content.replace("# PROPOSAL: ", "# ")
            content = content.replace("## PROPOSAL: ", "## ")
            
            target_path.write_text(content)
            promoted_count += 1
            
            # Optional: Move the original to archive instead of deleting?
            # For now, we leave it in docs/proposals but it's mirrored in knowledge.
            # Or we could delete it to "finalize" it. Let's delete it to avoid drift.
            item.unlink()

    print(f"✅ Promotion complete. {promoted_count} proposals finalized.")

if __name__ == "__main__":
    promote_active_proposals()
