#!/usr/bin/env python3
import os
import sys
import re
from pathlib import Path

# Antigravity Standard: Path Resolution
sys.path.append(str(Path(__file__).resolve().parent))
from lib.paths import REPO_ROOT

AGENT_DIR = REPO_ROOT / ".agent" / "agents"

def audit_agent(path: Path):
    content = path.read_text(encoding="utf-8")
    issues = []
    
    # Check Frontmatter
    if not content.startswith("---"):
        issues.append("Missing frontmatter (---)")
    
    # Extract frontmatter
    fm_match = re.search(r'^---\n(.*?)\n---', content, re.DOTALL)
    if not fm_match:
        issues.append("Invalid frontmatter structure")
        return issues
        
    fm = fm_match.group(1)
    
    # Check skills field
    if "skills:" not in fm:
        issues.append("Missing 'skills:' field in frontmatter")
    else:
        skills = re.search(r'skills:\s*(.*)', fm)
        if skills:
            skill_list = [s.strip() for s in skills.group(1).split(',')]
            # Mandatory Skills
            mandatory = ["clean-code"]
            for m in mandatory:
                if m not in skill_list:
                    issues.append(f"Missing mandatory skill: {m}")
        else:
            issues.append("Empty 'skills:' field")
            
    # Check if text references tools but frontmatter doesn't have skills
    tools_referenced = re.findall(r'`([\w_-]+\.py)`', content)
    if tools_referenced and "skills:" not in fm:
        issues.append(f"References tools {tools_referenced} but missing skills mapping")

    return issues

def main():
    print("🕵️  Agent Skill Audit starting...")
    all_agents = list(AGENT_DIR.glob("*.md"))
    total_issues = 0
    
    for agent_path in all_agents:
        issues = audit_agent(agent_path)
        if issues:
            print(f"\n❌ {agent_path.name}:")
            for issue in issues:
                print(f"  - {issue}")
            total_issues += len(issues)
            
    if total_issues == 0:
        print("\n✅ All agents are compliant with skill protocols.")
    else:
        print(f"\n🛑 Total issues found: {total_issues}")
        sys.exit(1)

if __name__ == "__main__":
    main()
