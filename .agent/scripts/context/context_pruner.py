#!/usr/bin/env python3
"""Context Pruner - Cognitive Load Management for the Archivist Agent.
Removes transient objects and summarizes long-term events in the Context Bus.
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
from datetime import datetime, timedelta

# Configuration
BUS_PATH = REPO_ROOT / ".agent" / "bus"
MAX_EVENT_AGE_DAYS = 7
PRUNE_PRIORITY_LOW = 1  # Transient/Debug
PRUNE_PRIORITY_HIGH = 10 # Decision/ADR

def prune_bus():
    if not BUS_PATH.exists():
        return {"status": "error", "message": "Bus path not found"}

    pruned_count = 0
    summarized_count = 0
    
    # Iterate through all files in the bus
    for bus_file in BUS_PATH.glob("*.json"):
        try:
            with open(bus_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 1. Prune by age and priority
            created_at = data.get("created_at")
            priority = data.get("priority", 5)
            
            if created_at:
                created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                age = datetime.now() - created_dt.replace(tzinfo=None)
                
                # If old and low priority, delete
                if age.days > MAX_EVENT_AGE_DAYS and priority < 5:
                    bus_file.unlink()
                    pruned_count += 1
                    continue
            
            # 2. Summarize transient logs if they are too large
            if data.get("type") == "log_stream" and bus_file.stat().st_size > 50000:
                # Keep only first 20 and last 20 lines
                logs = data.get("payload", [])
                if len(logs) > 100:
                    data["payload"] = logs[:20] + ["... [PRUNED] ..."] + logs[-20:]
                    data["is_pruned"] = True
                    with open(bus_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2)
                    summarized_count += 1

        except Exception:
            pass

    return {
        "status": "success",
        "pruned": pruned_count,
        "summarized": summarized_count,
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    result = prune_bus()
    print(json.dumps(result, indent=2))
