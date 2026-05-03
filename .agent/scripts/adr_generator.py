#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess
import json
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
DECISIONS_DIR = REPO_ROOT / "wiki" / "decisions"
TEMPLATE_PATH = REPO_ROOT / ".agent" / "wiki-templates" / "DECISIONS.md"
DRIFT_DETECTOR = REPO_ROOT / ".agent" / "scripts" / "drift_detector.py"

def get_drifts():
    if not DRIFT_DETECTOR.exists():
        return []
    try:
        res = subprocess.run(["python3", str(DRIFT_DETECTOR), "--format", "json"], 
                             cwd=str(REPO_ROOT), capture_output=True, text=True)
        if res.returncode == 0:
            data = json.loads(res.stdout)
            return data.get("drifts", [])
    except:
        pass
    return []

def slugify(text):
    import re
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return text.strip('-')

def create_adr_draft(filename):
    DECISIONS_DIR.mkdir(exist_ok=True, parents=True)
    
    today = datetime.now().strftime("%Y-%m-%d")
    base_name = Path(filename).stem
    slug = slugify(base_name)
    adr_filename = f"{today}-{slug}.md"
    adr_path = DECISIONS_DIR / adr_filename
    
    if adr_path.exists():
        return None, f"ADR already exists: {adr_filename}"
    
    template_content = ""
    if TEMPLATE_PATH.exists():
        template_content = TEMPLATE_PATH.read_text(encoding='utf-8')
    else:
        template_content = f"# ADR: Change in {filename}\n\n## Status\nDraft\n\n## Context\n\n## Decision\n\n## Consequences\n"

    # Minimal replacement
    content = template_content.replace("[Decision Title]", f"Architectural Change in {filename}")
    content = content.replace("YYYY-MM-DD", today)
    content = content.replace("Proposed / Accepted / Deprecated", "Draft")
    content = content.replace("[agent or person]", "Antigravity Agent")
    
    # Ensure the filename is mentioned for drift_detector
    content += f"\n\n**Related Component:** `{filename}`\n"
    
    adr_path.write_text(content, encoding='utf-8')
    return adr_path, None

def main():
    parser = argparse.ArgumentParser(description="ADR Generator - Create draft ADRs based on documentation drift")
    parser.add_argument("--all", action="store_true", help="Generate drafts for all drifting files")
    parser.add_argument("--file", help="Specific file to generate ADR for")
    args = parser.parse_args()

    files_to_process = []
    if args.file:
        files_to_process = [args.file]
    elif args.all:
        files_to_process = get_drifts()
    
    if not files_to_process:
        print("No files to process for ADR generation.")
        return

    print(f"🔍 Generating ADR drafts for {len(files_to_process)} file(s)...")
    for f in files_to_process:
        path, error = create_adr_draft(f)
        if error:
            print(f"  ❌ {f}: {error}")
        else:
            print(f"  ✅ {f} → {path.relative_to(REPO_ROOT)}")

    print("\nNext steps: Edit the generated drafts to explain the architectural 'Why' and 'Gestalt'.")

if __name__ == "__main__":
    main()
