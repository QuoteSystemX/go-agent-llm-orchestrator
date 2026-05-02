#!/usr/bin/env python3
import os
import subprocess
from pathlib import Path
import argparse
import json
import re

REPO_ROOT = Path(__file__).parent.parent.parent

def get_git_changes():
    files = []
    try:
        if not (REPO_ROOT / ".git").exists():
            return []
        # Try to get changes from last 5 commits
        try:
            res = subprocess.check_output(["git", "diff", "--name-only", "HEAD~5"], cwd=REPO_ROOT, stderr=subprocess.DEVNULL)
            files.extend(res.decode().split("\n"))
        except:
            # Fallback to all tracked files if HEAD~5 is too deep
            res = subprocess.check_output(["git", "ls-files"], cwd=REPO_ROOT)
            files.extend(res.decode().split("\n"))
            
        # Get untracked files
        untracked = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard"], cwd=REPO_ROOT)
        files.extend(untracked.decode().split("\n"))
        
        return list(set([f for f in files if f]))
    except Exception as e:
        print(f"⚠️ Git error: {e}")
        return []

def get_documented_files():
    docs = []
    # Read ARCHITECTURE.md from .agent/
    arch = REPO_ROOT / ".agent" / "ARCHITECTURE.md"
    if arch.exists():
        docs.append(arch.read_text(encoding='utf-8', errors='ignore'))
    
    # Read wiki
    wiki_dir = REPO_ROOT / "wiki"
    if wiki_dir.exists():
        for f in wiki_dir.glob("**/*.md"):
            try:
                docs.append(f.read_text(encoding='utf-8', errors='ignore'))
            except:
                pass
            
    return "\n".join(docs)

def check_arch_consistency():
    """Verify that all agents and skills listed in ARCHITECTURE.md actually exist."""
    arch_path = REPO_ROOT / ".agent" / "ARCHITECTURE.md"
    if not arch_path.exists():
        return []
    
    content = arch_path.read_text(encoding='utf-8')
    drifts = []
    
    # Split content by H2 headers (##) to isolate Agents from Skills
    sections = re.split(r'^## ', content, flags=re.MULTILINE)
    
    agent_dir = REPO_ROOT / ".agent" / "agents"
    # Skills can be in multiple locations
    skill_dirs = [
        REPO_ROOT / ".agent" / "skills",
        REPO_ROOT / ".agent" / ".shared"
    ]
    
    def skill_exists(name):
        return any((sd / name).is_dir() for sd in skill_dirs)

    for section in sections:
        header = section.split('\n')[0].lower()
        # Find names in the FIRST column of tables
        names = re.findall(r'^\|\s*`([\w-]+)`\s*\|', section, re.MULTILINE)
        
        # Section identification logic
        is_agents_section = "agent" in header and "lifecycle" not in header and "skill" not in header
        is_skills_section = "skill" in header
        
        if is_agents_section:
            for name in names:
                if name.lower() in ["agent", "agent-name"]: continue
                if not (agent_dir / f"{name}.md").exists():
                    drifts.append(f"AGENT DRIFT: '{name}' listed in Agents table but missing in .agent/agents/")
        
        elif is_skills_section:
            for name in names:
                if name.lower() in ["skill", "skill-name"]: continue
                if not skill_exists(name):
                    drifts.append(f"SKILL DRIFT: '{name}' listed in Skills table but missing in {skill_dirs[0]} or {skill_dirs[1]}")

    return drifts

def detect_drift():
    changes = get_git_changes()
    docs_content = get_documented_files()
    
    drifts = check_arch_consistency()
    # Filter for important files (code, not assets/logs)
    monitored_exts = [".go", ".ts", ".tsx", ".py", ".js"]
    
    for f in changes:
        path = Path(f)
        if path.suffix in monitored_exts and "test" not in f:
            # print(f"Checking {f}...") # Debug
            # Check if filename is mentioned in docs
            if path.name not in docs_content:
                drifts.append(f"FILE DRIFT: {f} (modified but not in docs)")
                
    return drifts

def main():
    parser = argparse.ArgumentParser(description="Detect Documentation Drift")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    args = parser.parse_args()

    drifts = detect_drift()
    
    if args.format == "json":
        print(json.dumps({
            "drifts": drifts,
            "passed": len(drifts) == 0,
            "count": len(drifts)
        }))
        return

    print("🔍 Checking for Documentation Drift (Code vs Wiki)...")
    if drifts:
        print("\n⚠️  WARNING: Found modified files not mentioned in documentation:")
        for d in drifts:
            print(f"  - {d}")
        print("\nRecommendation: Update ARCHITECTURE.md or Wiki using 'wiki-architect' and 'analyst'.")
    else:
        print("✅ Documentation is in sync with recent code changes.")

if __name__ == "__main__":
    main()
