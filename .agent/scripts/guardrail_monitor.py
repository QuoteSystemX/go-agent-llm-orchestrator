#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
TELEMETRY_PATH = REPO_ROOT / ".agent" / "bus" / "telemetry.json"
RULES_PATH = REPO_ROOT / ".agent" / "config" / "watchdog_rules.json"

def load_json(path):
    if not path.exists():
        return {}
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except:
        return {}

def check_guardrails():
    rules = load_json(RULES_PATH)
    telemetry = load_json(TELEMETRY_PATH)
    
    if not rules or not telemetry:
        return True, "No rules or telemetry found."

    limits = rules.get("limits", {})
    
    # Check total cost/tokens for current session/task
    total_tokens = telemetry.get("total_tokens", 0)
    total_cost = telemetry.get("total_cost_usd", 0)
    
    if total_tokens > limits.get("token_budget_per_task", 100000):
        return False, f"TOKEN BUDGET EXCEEDED: {total_tokens} > {limits['token_budget_per_task']}"
        
    if total_cost > limits.get("cost_limit_per_task_usd", 2.0):
        return False, f"COST LIMIT EXCEEDED: ${total_cost:.2f} > ${limits['cost_limit_per_task_usd']:.2f}"

    # Check for consecutive failures (logic simplified for this version)
    # In a real scenario, we'd parse the log of actions.
    
    return True, "All systems within safety bounds."

if __name__ == "__main__":
    ok, msg = check_guardrails()
    if not ok:
        print(f"🛑 WATCHDOG ALERT: {msg}")
        sys.exit(1)
    else:
        print(f"✅ Watchdog: {msg}")
        sys.exit(0)
