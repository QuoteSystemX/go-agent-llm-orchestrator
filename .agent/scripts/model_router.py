#!/usr/bin/env python3
"""Dynamic Model Router — selects the optimal model tier for a task.

Reads router_rules.json for keyword→complexity mapping.
Model IDs support env-var fallback syntax: ${ENV_VAR:-default_value}

Usage:
    python3 model_router.py "debug auth flow"
    python3 model_router.py "fix typo" --model claude-opus-4-20250514
    MODEL_L1=my-model python3 model_router.py "lint code"
"""
import json
import sys
import os
import re
import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
RULES_FILE = REPO_ROOT / ".agent" / "config" / "router_rules.json"


def load_rules():
    if not RULES_FILE.exists():
        return None
    with open(RULES_FILE, "r") as f:
        return json.load(f)


def resolve_env_var(value: str) -> str:
    """Resolve ${ENV_VAR:-default} syntax in model IDs.

    Examples:
        "${MODEL_L1:-claude-sonnet-4-20250514}" → env(MODEL_L1) or "claude-sonnet-4-20250514"
        "claude-opus-4-20250514" → "claude-opus-4-20250514" (passthrough)
    """
    match = re.match(r'^\$\{(\w+):-([^}]+)\}$', value)
    if match:
        env_name, default = match.group(1), match.group(2)
        return os.environ.get(env_name, default)
    return value


def route(task_description, override_model=None):
    rules = load_rules()
    if not rules:
        return override_model or "claude-sonnet-4-20250514"

    # 1. Manual Override — highest priority
    if override_model:
        print(f"🤖 **Manual Override**: Using model `{override_model}` as requested.")
        return override_model

    # 2. Analyze Complexity via keyword matching
    selected_complexity = "L2"  # Default
    desc_lower = task_description.lower()

    for rule in rules.get("rules", []):
        if any(kw in desc_lower for kw in rule.get("keywords", [])):
            selected_complexity = rule["complexity"]
            break

    # 3. Resolve Model ID (with env-var support)
    raw_model_id = rules.get("models", {}).get(selected_complexity, "claude-sonnet-4-20250514")
    model_id = resolve_env_var(raw_model_id)

    # 4. Check Environment Availability
    available = os.environ.get("AVAILABLE_MODELS", "")
    if available and model_id not in available:
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
