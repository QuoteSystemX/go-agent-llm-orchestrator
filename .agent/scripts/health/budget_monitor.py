#!/usr/bin/env python3
"""
Budget Monitor - Token Usage & Hard Limits
Tracks spending across agent sessions and enforces safety limits.
"""

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    import sys
    from pathlib import Path
    SCRIPTS_DIR = Path(__file__).resolve().parents[1]
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.append(str(SCRIPTS_DIR))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev"]:
        d_path = str(SCRIPTS_DIR / domain)
        if d_path not in sys.path:
            sys.path.append(d_path)

import os
import json
import sys
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parents[3]
BUS_DIR = REPO_ROOT / ".agent" / "bus"
GUARDRAILS_FILE = REPO_ROOT / ".agent" / "rules" / "guardrails.json"

DEFAULT_LIMITS = {
    "daily_token_limit": 500000,
    "session_token_limit": 50000,
    "cost_limit_usd": 10.0
}

def load_guardrails():
    if GUARDRAILS_FILE.exists():
        try:
            with open(GUARDRAILS_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_LIMITS

def get_current_usage() -> int:
    """Sum token usage from bus telemetry events.

    Reads all telemetry*.json files from BUS_DIR via lib/data_sources.
    Token proxy strategy (in priority order):
      1. event["eval_count"] + event["prompt_eval_count"]  (Ollama native fields)
      2. event["tokens_used"]                               (custom field)
      3. Fallback: count routing events * AVG_TOKENS_PER_EVENT (heuristic)

    Returns 0 when no telemetry is available — never raises.
    """
    AVG_TOKENS_PER_EVENT = 500  # heuristic when no token fields present

    try:
        from lib.data_sources import read_bus_telemetry
        events = read_bus_telemetry(BUS_DIR)
    except Exception:
        events = []

    if not events:
        return 0

    total = 0
    has_token_fields = False
    routing_count = 0

    for ev in events:
        if not isinstance(ev, dict):
            continue

        eval_count = ev.get("eval_count", 0) or 0
        prompt_eval = ev.get("prompt_eval_count", 0) or 0
        tokens_used = ev.get("tokens_used", 0) or 0

        if eval_count or prompt_eval or tokens_used:
            total += eval_count + prompt_eval + tokens_used
            has_token_fields = True
        elif ev.get("type") == "routing":
            routing_count += 1

    if not has_token_fields:
        # Heuristic fallback: routing events as token proxy
        total = routing_count * AVG_TOKENS_PER_EVENT

    return int(total)

def main() -> None:
    print(f"\n{'='*60}")
    print(f"💰 BUDGET WARDEN - Priority Guard")
    print(f"{'='*60}")
    
    limits = load_guardrails()
    usage = get_current_usage()
    
    percent = (usage / limits['session_token_limit']) * 100
    priority = os.environ.get("TASK_PRIORITY", "MEDIUM").upper()
    
    print(f"Tokens Used: {usage:,} / {limits['session_token_limit']:,} ({percent:.1f}%)")
    print(f"Current Task Priority: {priority}")
    
    status = "OK"
    # Warden Logic:
    if percent > 100:
        status = "BLOCKED"
        print("❌ ERROR: Budget limit EXCEEDED. Blocking execution.")
    elif percent > 90:
        status = "CRITICAL"
        print("⚠️  WARNING: Budget limit reached 90%!")
    elif percent > 50 and priority == "LOW":
        status = "THROTTLED"
        print("👮 Warden: Throttling LOW priority task (Budget > 50%)")
    
    # Export for status_report
    BUS_DIR.mkdir(parents=True, exist_ok=True)
    with open(BUS_DIR / "budget_status.json", "w") as f:
        json.dump({
            "status": status,
            "usage": usage,
            "limit": limits['session_token_limit'],
            "percent": percent,
            "priority": priority,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }, f, indent=2)
    
    if status in ["BLOCKED", "THROTTLED"]:
        sys.exit(1)

if __name__ == "__main__":
    main()
