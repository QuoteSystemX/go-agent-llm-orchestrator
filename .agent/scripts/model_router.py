#!/usr/bin/env python3
import json
import sys
import os
import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
RULES_FILE = REPO_ROOT / ".agent" / "config" / "router_rules.json"

def load_rules():
    if not RULES_FILE.exists():
        return None
    with open(RULES_FILE, "r") as f:
        return json.load(f)

def route(task_description, override_model=None):
    rules = load_rules()
    if not rules:
        return override_model or "claude-3-5-sonnet-20240620"

    # 1. Manual Override
    if override_model:
        print(f"🤖 **Manual Override**: Using model `{override_model}` as requested.")
        return override_model

    # 2. Analyze Complexity
    selected_complexity = "L2"  # Default
    desc_lower = task_description.lower()
    
    for rule in rules["rules"]:
        if any(kw in desc_lower for kw in rule["keywords"]):
            selected_complexity = rule["complexity"]
            break
            
    # 3. Model Mapping
    model_id = rules["models"].get(selected_complexity, "claude-3-5-sonnet-20240620")
    
    # 4. Check Environment Availability (Mockup for single-model test)
    available = os.environ.get("AVAILABLE_MODELS", "")
    if available and model_id not in available:
        # If model not available, fallback to the first available or default
        fallback_model = available.split(",")[0]
        print(f"🤖 **Environment Routing**: Model `{model_id}` not available. Falling back to `{fallback_model}`.")
        return fallback_model

    print(f"🤖 **Dynamic Routing**: Selected `{model_id}` for {selected_complexity} task.")
    return model_id

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Model Router")
    parser.add_argument("task", help="Description of the task")
    parser.add_argument("--model", help="Manual model override")
    args = parser.parse_args()
    
    print(route(args.task, args.model))
