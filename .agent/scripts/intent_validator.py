#!/usr/bin/env python3
import os
import sys
import re
from pathlib import Path

# Antigravity Standard: Path Resolution
sys.path.append(str(Path(__file__).resolve().parent))
from lib.paths import REPO_ROOT

def get_arch_context() -> str:
    arch_path = REPO_ROOT / ".agent" / "ARCHITECTURE.md"
    adr_dir = REPO_ROOT / "wiki" / "decisions"
    
    context = []
    if arch_path.exists():
        context.append(arch_path.read_text(encoding="utf-8"))
    
    if adr_dir.exists():
        for adr in adr_dir.glob("*.md"):
            context.append(adr.read_text(encoding="utf-8"))
            
    return "\n\n".join(context).lower()

def validate_intent(intent: str):
    intent = intent.lower()
    context = get_arch_context()
    
    conflicts = []
    
    # Technology Stack Heuristics
    tech_stack = {
        "database": ["postgresql", "mongodb", "clickhouse", "redis", "mysql", "sqlite"],
        "language": ["go", "python", "typescript", "javascript", "rust", "java", "c#"],
        "api": ["rest", "grpc", "graphql", "trpc"]
    }
    
    for category, techs in tech_stack.items():
        # Check if intent mentions a tech
        for tech in techs:
            if tech in intent:
                # Check if this tech is in our context
                if tech not in context:
                    # Find what IS in our context for this category
                    current_techs = [t for t in techs if t in context]
                    if current_techs:
                        conflicts.append(f"⚠️  Intent uses '{tech}' ({category}), but project currently uses {current_techs}. This might violate ADR standards.")
                    else:
                        conflicts.append(f"ℹ️  New technology '{tech}' detected. Ensure an ADR is created if this is a permanent addition.")

    return conflicts

def main():
    if len(sys.argv) < 2:
        print("Usage: intent_validator.py '<intent>'")
        sys.exit(1)
        
    intent = " ".join(sys.argv[1:])
    print(f"🛡️  Validating Intent: '{intent}'...")
    
    conflicts = validate_intent(intent)
    
    if not conflicts:
        print("✅ Intent appears consistent with current architecture.")
        sys.exit(0)
    else:
        print("\n🚩 Potential Conflicts/Warnings found:")
        for c in conflicts:
            print(f"  - {c}")
        sys.exit(0) # We don't block yet, just warn

if __name__ == "__main__":
    main()
