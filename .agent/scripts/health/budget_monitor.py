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
        except:
            pass
    return DEFAULT_LIMITS

def get_current_usage():
    """
    Sum up token usage from bus events.
    In a real implementation, this would parse all telemetry logs.
    """
    total_tokens = 0
    # Simulate extraction from bus for this task
    # In practice: for f in BUS_DIR.glob("telemetry-*.json"): ...
    return 15000 # Mocked current usage for demonstration

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
    if percent > 50 and priority == "LOW":
        status = "THROTTLED"
        print("👮 Warden: Throttling LOW priority task (Budget > 50%)")
    elif percent > 90:
        status = "CRITICAL"
        print("⚠️  WARNING: Budget limit reached 90%!")
    elif percent > 100:
        status = "BLOCKED"
        print("❌ ERROR: Budget limit EXCEEDED. Blocking execution.")
    
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
