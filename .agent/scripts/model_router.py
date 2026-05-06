#!/usr/bin/env python3
"""Unified Model Router 2.1 — Adaptive Intelligence with L4 support.

Integrated with Experience Distiller, Guardrail Monitor, and next-gen models (Claude 4.6, GPT-OSS).
"""
import json
import sys
import os
import re
import argparse
from pathlib import Path

# Setup paths
REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))

try:
    from lib.paths import RULES_FILE, TELEMETRY_PATH, LESSONS_PATH
    from lib.common import load_json_safe
except ImportError:
    RULES_FILE = REPO_ROOT / ".agent" / "config" / "router_rules.json"
    TELEMETRY_PATH = REPO_ROOT / ".agent" / "bus" / "telemetry.json"
    LESSONS_PATH = REPO_ROOT / "wiki" / "KNOWLEDGE.md"
    def load_json_safe(path):
        if not Path(path).exists(): return {}
        try:
            with open(path, 'r') as f: return json.load(f)
        except: return {}

def log_routing_event(task, score, tier, model_id):
    """Log the routing decision to telemetry.json for transparency."""
    try:
        telemetry = load_json_safe(TELEMETRY_PATH)
        if "events" not in telemetry: telemetry["events"] = []
        
        from datetime import datetime
        event = {
            "timestamp": datetime.now().isoformat(),
            "type": "routing",
            "task": task[:100] + "..." if len(task) > 100 else task,
            "score": score,
            "tier": tier,
            "model_id": model_id
        }
        
        telemetry["events"].append(event)
        # Keep only last 50 events
        if len(telemetry["events"]) > 50:
            telemetry["events"] = telemetry["events"][-50:]
            
        with open(TELEMETRY_PATH, 'w') as f:
            json.dump(telemetry, f, indent=2)
    except Exception as e:
        print(f"⚠️ Telemetry log failed: {e}")

def detect_provider():
    if os.environ.get("AGENT_PROVIDER"):
        return os.environ.get("AGENT_PROVIDER").lower()
    # Default to antigravity for this environment
    return "antigravity"

def get_failure_score(task_description):
    """Check for historical failures in KNOWLEDGE.md."""
    try:
        if not LESSONS_PATH.exists(): return 0
        content = LESSONS_PATH.read_text().lower()
        keywords = re.findall(r'\b\w{4,}\b', task_description.lower())
        
        failure_count = 0
        for kw in keywords:
            if kw in content:
                idx = content.find(kw)
                context = content[max(0, idx-100):min(len(content), idx+200)]
                if any(word in context for word in ["fail", "error", "retry", "broken", "bug", "hallucination"]):
                    failure_count += 1
        
        return min(failure_count, 3) 
    except Exception:
        return 0

def get_budget_penalty():
    """Check budget status from telemetry."""
    telemetry = load_json_safe(TELEMETRY_PATH)
    watchdog = load_json_safe(REPO_ROOT / ".agent" / "config" / "watchdog_rules.json")
    
    cost = telemetry.get("total_cost_usd", 0)
    limit = watchdog.get("limits", {}).get("cost_limit_per_task_usd", 2.0)
    
    if cost > (limit * 0.85): # 85% budget spent
        return -3 # Heavier penalty for L4 models
    return 0

def calculate_score(task_desc, rules):
    scoring = rules.get("scoring", {})
    weights = scoring.get("weights", {})
    
    score = 5 # Base score (L2)
    desc_lower = task_desc.lower()
    
    # 1. Keyword weights
    for kw, weight in weights.items():
        if kw in desc_lower:
            score += weight
            
    # 2. History bonus
    score += get_failure_score(task_desc)
    
    # 3. Budget penalty
    score += get_budget_penalty()
    
    return max(1, min(score, 18)) # Max score increased to 18 for L4

def route(task_description, override_model=None):
    current_provider = detect_provider()
    rules = load_json_safe(RULES_FILE)
    
    if override_model:
        return override_model

    # 1. Calculate Score
    score = calculate_score(task_description, rules)
    thresholds = rules.get("scoring", {}).get("thresholds", {"L1": 3, "L2": 7, "L3": 10, "L4": 13})
    
    if score <= thresholds["L1"]:
        tier = "L1"
    elif score <= thresholds["L2"]:
        tier = "L2"
    elif score <= thresholds["L3"]:
        tier = "L3"
    else:
        tier = "L4"

    # 2. Domain Affinity
    affinity = rules.get("domain_affinity", {})
    target_provider = current_provider
    for domain, pref in affinity.items():
        if domain in task_description.lower():
            target_provider = pref
            break

    # 3. Resolve Model ID
    model_map = rules.get("models", {}).get(target_provider, rules.get("models", {}).get("antigravity", {}))
    model_id = model_map.get(tier, "gemini-3-flash")

    # Log Routing Insights
    print(f"🤖 **Adaptive Routing 2.1**:")
    print(f"   ├─ Score: {score}/18 -> Tier: {tier}")
    print(f"   ├─ Affinity: {target_provider.upper()}")
    print(f"   └─ Selected: `{model_id}`")
    
    # Record to telemetry for transparency
    log_routing_event(task_description, score, tier, model_id)
    
    return model_id

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("task")
    parser.add_argument("--model", help="Manual override")
    args = parser.parse_args()
    print(route(args.task, args.model))
