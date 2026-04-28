#!/usr/bin/env python3
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent

def get_git_changes():
    try:
        # Get list of files modified in the last 5 commits
        res = subprocess.check_output(["git", "diff", "--name-only", "HEAD~5"], cwd=REPO_ROOT)
        return [f for f in res.decode().split("\n") if f]
    except:
        return []

def get_documented_files():
    docs = []
    # Read ARCHITECTURE.md from .agent/
    arch = REPO_ROOT / ".agent" / "ARCHITECTURE.md"
    if arch.exists():
        docs.append(arch.read_text())
    
    # Read wiki
    wiki_dir = REPO_ROOT / "wiki"
    if wiki_dir.exists():
        for f in wiki_dir.glob("**/*.md"):
            docs.append(f.read_text())
            
    return "\n".join(docs)

def detect_drift():
    changes = get_git_changes()
    docs_content = get_documented_files()
    
    drifts = []
    # Filter for important files (code, not assets/logs)
    monitored_exts = [".go", ".ts", ".tsx", ".py", ".js"]
    
    for f in changes:
        path = Path(f)
        if path.suffix in monitored_exts and "test" not in f:
            # Check if filename is mentioned in docs
            if path.name not in docs_content:
                drifts.append(f)
                
    return drifts

if __name__ == "__main__":
    print("🔍 Checking for Documentation Drift (Code vs Wiki)...")
    drifts = detect_drift()
    if drifts:
        print("\n⚠️  WARNING: Found modified files not mentioned in documentation:")
        for d in drifts:
            print(f"  - {d}")
        print("\nRecommendation: Update ARCHITECTURE.md or Wiki using 'wiki-architect' and 'analyst'.")
    else:
        print("✅ Documentation is in sync with recent code changes.")
