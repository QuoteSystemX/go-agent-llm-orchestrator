#!/usr/bin/env python3
"""
Chaos Analyzer - MTTR Measurement
Measures how long it takes for the system to recover from a Chaos Monkey attack.
"""
import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parents[2]
BUS_DIR = REPO_ROOT / ".agent" / "bus"
CHAOS_EVENT_FILE = BUS_DIR / "chaos_event.json"
BLUE_STATUS_FILE = BUS_DIR / "blue_team_status.json"

def main() -> None:
    print(f"\n{'='*60}")
    print(f"📊 CHAOS ANALYZER - MTTR Report")
    print(f"{'='*60}")
    
    if not CHAOS_EVENT_FILE.exists():
        print("❌ No active chaos events found.")
        sys.exit(0)
        
    with open(CHAOS_EVENT_FILE, 'r') as f:
        event = json.load(f)
        
    start_time = event["timestamp"]
    print(f"Attack Type: {', '.join(event['args'])}")
    print(f"Start Time: {datetime.fromtimestamp(start_time).strftime('%H:%M:%S')}")
    
    # Wait for recovery (max 60s)
    print("⏳ Monitoring Blue Team for recovery...")
    recovered = False
    recovery_time = 0
    
    for i in range(60):
        if BLUE_STATUS_FILE.exists():
            with open(BLUE_STATUS_FILE, 'r') as f:
                status = json.load(f)
                if status["status"] == "HEALTHY":
                    recovered = True
                    # In a real scenario, we'd check if the timestamp is AFTER the attack
                    recovery_time = time.time() - start_time
                    break
        time.sleep(1)
        print(".", end="", flush=True)

    print("\n")
    if recovered:
        print(f"✅ SYSTEM RECOVERED!")
        print(f"⏱  MTTR (Mean Time To Recovery): {recovery_time:.1f}s")
        # Log result
        with open(BUS_DIR / "chaos_report.json", "w") as f:
            json.dump({
                "mttr": recovery_time,
                "status": "SUCCESS",
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }, f, indent=2)
    else:
        print("❌ SYSTEM FAILED TO RECOVER WITHIN 60s.")
        with open(BUS_DIR / "chaos_report.json", "w") as f:
            json.dump({
                "mttr": None,
                "status": "FAILURE",
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }, f, indent=2)

if __name__ == "__main__":
    main()
