#!/usr/bin/env python3
"""Unified Model Router — selects the optimal model tier for a task.

Supports both Antigravity (Gemini) and Cloud Core (Claude) ecosystems.
Detects provider via AGENT_PROVIDER env var or heuristic analysis.

Usage:
    python3 model_router.py "debug auth flow"
"""
import json
import sys
import os
import re
import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
RULES_FILE = REPO_ROOT / ".agent" / "config" / "router_rules.json"

# Default Model Mapping by Provider
PROVIDER_DEFAULTS = {
    "antigravity": {
        "L1": "gemini-1.5-flash",
        "L2": "gemini-1.5-flash",
        "L3": "gemini-1.5-pro"
    },
    "cloud-core": {
        "L1": "claude-3-haiku-20240307",
        "L2": "claude-3-5-sonnet-20240620",
        "L3": "claude-3-5-sonnet-20240620"
    },
    "default": {
        "L1": "gpt-4o-mini",
        "L2": "claude-sonnet-4-20250514",
        "L3": "o1-preview"
    }
}

def detect_provider():
    """Detect if we are running in Antigravity or Cloud Core."""
    if os.environ.get("AGENT_PROVIDER"):
        return os.environ.get("AGENT_PROVIDER").lower()
    
    # Heuristics
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("ANTIGRAVITY_APP_DATA_DIR"):
        return "antigravity"
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLOUD_CORE_HOME"):
        return "cloud-core"
    
    return "default"

def load_rules():
    if not RULES_FILE.exists():
        return None
    with open(RULES_FILE, "r") as f:
        return json.load(f)

def resolve_env_var(value: str, provider: str = "default", tier: str = "L2") -> str:
    """Resolve ${ENV_VAR:-default} syntax in model IDs with provider awareness."""
    match = re.match(r'^\$\{(\w+):-([^}]+)\}$', value)
    if match:
        env_name, default_val = match.group(1), match.group(2)
        # If default is generic sonnet from rules, override with provider default if possible
        if "sonnet" in default_val.lower() or "opus" in default_val.lower():
            default_val = PROVIDER_DEFAULTS.get(provider, {}).get(tier, default_val)
        return os.environ.get(env_name, default_val)
    return value

def route(task_description, override_model=None):
    provider = detect_provider()
    rules = load_rules()
    
    # 1. Manual Override — highest priority
    if override_model:
        print(f"🤖 **Manual Override**: Using model `{override_model}` as requested.")
        return override_model

    # 2. Analyze Complexity via keyword matching
    selected_complexity = "L2"  # Default
    desc_lower = task_description.lower()

    if rules:
        for rule in rules.get("rules", []):
            if any(kw in desc_lower for kw in rule.get("keywords", [])):
                selected_complexity = rule["complexity"]
                break

    # 3. Resolve Model ID
    if rules:
        raw_model_id = rules.get("models", {}).get(selected_complexity, "L2")
        model_id = resolve_env_var(raw_model_id, provider, selected_complexity)
    else:
        model_id = PROVIDER_DEFAULTS.get(provider, {}).get(selected_complexity)

    # 4. Check Environment Availability (Skip if using provider defaults directly)
    available = os.environ.get("AVAILABLE_MODELS", "")
    if available and model_id not in available:
        fallback_model = available.split(",")[0]
        print(f"🤖 **Environment Routing**: Model `{model_id}` not available. Falling back to `{fallback_model}`.")
        return fallback_model

    print(f"🤖 **Unified Routing**: [{provider.upper()}] Selected `{model_id}` for {selected_complexity} task.")
    return model_id

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Unified AI Model Router")
    parser.add_argument("task", help="Description of the task")
    parser.add_argument("--model", help="Manual model override")
    args = parser.parse_args()

    print(route(args.task, args.model))
