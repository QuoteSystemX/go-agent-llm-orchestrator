#!/usr/bin/env python3
"""Router Trainer 1.0 — Experience-Driven Weight Optimization.

Analyzes LESSONS_LEARNED.md for failure patterns and automatically adjusts
routing weights in router_rules.json to prevent similar issues in the future.
"""
import json
import sys
import re
from pathlib import Path

# Setup paths
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RULES_FILE = REPO_ROOT / ".agent" / "config" / "router_rules.json"
LESSONS_FILE = REPO_ROOT / ".agent" / "rules" / "LESSONS_LEARNED.md"

def load_json(path):
    if not path.exists(): return {}
    with open(path, 'r') as f:
        return json.load(f)

def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def extract_lessons(content):
    """Split LESSONS_LEARNED.md into individual lesson blocks."""
    return re.split(r'\n### ', content)

def train():
    if not RULES_FILE.exists():
        return "❌ Error: router_rules.json not found."
    if not LESSONS_FILE.exists():
        return "❌ Error: LESSONS_LEARNED.md not found."

    rules = load_json(RULES_FILE)
    content = LESSONS_FILE.read_text()
    lessons = extract_lessons(content)
    
    failure_markers = ["fail", "error", "broken", "bug", "hallucination", "missing", "drift", "narrow", "ignoring"]
    weights = rules.get("scoring", {}).get("weights", {})
    
    adjustments = []
    
    # 1. Adjust weights for existing keywords
    for kw, weight in weights.items():
        count = 0
        for lesson in lessons:
            lesson_lower = lesson.lower()
            if kw.lower() in lesson_lower:
                # Check if this lesson describes a failure/problem
                if any(marker in lesson_lower for marker in failure_markers):
                    count += 1
        
        if count > 0:
            # Increase weight: more failures = higher complexity for this keyword
            # Max weight capped at 15 to prevent L4-everything
            old_weight = weights[kw]
            boost = min(count, 3) # Cap boost per training cycle
            new_weight = min(old_weight + boost, 15)
            
            if new_weight != old_weight:
                weights[kw] = new_weight
                adjustments.append(f"📈 Boosted '{kw}': {old_weight} -> {new_weight} (found in {count} failure lessons)")

    # 2. Discover new keywords
    # If a term appears in multiple failure lessons but isn't a keyword, add it.
    potential_keywords = ["drift", "sync", "deployment", "infrastructure", "component"]
    for pk in potential_keywords:
        if pk not in weights:
            count = 0
            for lesson in lessons:
                if pk in lesson.lower() and any(m in lesson.lower() for m in failure_markers):
                    count += 1
            if count >= 2: # At least two failures to qualify as a new keyword
                weights[pk] = 5
                adjustments.append(f"✨ Added new keyword '{pk}' with weight 5")

    if not adjustments:
        return "✅ No adjustments needed. Router weights are optimal based on current experience."

    save_json(RULES_FILE, rules)
    
    report = ["🧠 **Router Training Report**", "---"] + adjustments
    return "\n".join(report)

if __name__ == "__main__":
    print(train())
