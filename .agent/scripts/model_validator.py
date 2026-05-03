#!/usr/bin/env python3
"""Mental Model Validator.

Checks proposed changes against MENTAL_MODELS.md to ensure architectural alignment.
Part of the Unified Cardinal Enhancements Phase 1 (Karpathy 2.0).
"""
import sys
import os
import json
from pathlib import Path

WIKI_DIR = Path("wiki/mental-models")

def load_mental_models():
    models = []
    if not WIKI_DIR.exists():
        return models
    for path in WIKI_DIR.rglob("*.md"):
        with open(path, "r") as f:
            models.append(f.read())
    return models

def validate_change(goal, impacted_files):
    print("🧠 Checking Architectural Alignment with Mental Models...")
    models = load_mental_models()
    if not models:
        print("⚠️ No mental models found. Skipping validation.")
        return True

    # Logic: Check for keywords in goal/files that trigger specific models
    # In a full implementation, this would call an LLM with the models as context.
    # For now, we use a heuristic approach.
    
    violations = []
    for model in models:
        # Example: Resilience-First model checks for destructive commands
        if "Resilience-First" in model:
            if "rm -rf" in goal or "delete" in goal.lower():
                violations.append("Violation of Resilience-First: Destructive commands detected.")
        
    if violations:
        for v in violations:
            print(f"❌ ARCHITECTURAL VETO: {v}")
        return False

    print("✅ Change aligns with current Mental Models.")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 model_validator.py <goal> <files_json>")
        sys.exit(1)
    
    goal = sys.argv[1]
    files = json.loads(sys.argv[2])
    
    success = validate_change(goal, files)
    sys.exit(0 if success else 1)
