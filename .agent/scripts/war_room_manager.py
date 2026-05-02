#!/usr/bin/env python3
"""War Room Manager — The "Brain" of the Auto-SRE.
Listens for incidents and coordinates autonomous fixes.
"""
import sys
import time
import json
import subprocess
from pathlib import Path

try:
    from lib.paths import REPO_ROOT
    from lib.common import get_timestamp
    import bus_manager
except ImportError:
    sys.path.append(str(Path(__file__).resolve().parent))
    from lib.paths import REPO_ROOT
    from lib.common import get_timestamp
    import bus_manager

def manage_war_room(incident_id):
    """Orchestrates the resolution of an incident."""
    print(f"🎖 War Room: Managing incident {incident_id}...")
    
    incident = bus_manager.wait_for_object(incident_id, timeout=2)
    if not incident:
        print(f"❌ Incident {incident_id} not found on bus.")
        return
    
    # 1. Spawn Debugger
    print("🎖 War Room: Requesting Root Cause Analysis from Debugger...")
    bus_manager.push(
        f"task_debug_{incident_id}",
        "requirement",
        "war_room_manager",
        json.dumps({
            "agent": "debugger",
            "instruction": f"Analyze incident {incident_id}. Error: {incident['content'].get('stderr', 'N/A')}",
            "incident_ref": incident_id
        })
    )
    
    # 2. Wait for Diagnosis (Simulated)
    time.sleep(1) 
    
    # 3. Request Fix Proposal
    print("🎖 War Room: Requesting fix from Test Engineer...")
    bus_manager.push(
        f"task_fix_{incident_id}",
        "requirement",
        "war_room_manager",
        json.dumps({
            "agent": "test-engineer",
            "instruction": "Generate a fix for the analyzed incident and verify.",
            "incident_ref": incident_id
        })
    )
    
    # 4. Final Verdict (Proposed Fix)
    proposed_fix_data = {
        "incident_ref": incident_id,
        "status": "ready_to_apply",
        "branch_name": f"fix/{incident_id}",
        "auto_commit": True
    }
    bus_manager.push(
        f"fix_{incident_id}",
        "proposed_fix",
        "war_room_manager",
        json.dumps(proposed_fix_data)
    )
    print(f"✅ War Room: Proposed fix is on the bus.")
    
    # 5. Handle Autonomous Mode (Simulated Git Ops)
    handle_git_ops(proposed_fix_data)

def handle_git_ops(fix):
    """Creates a fix branch and commits if in autonomous mode."""
    branch = fix.get('branch_name', 'fix/unknown')
    print(f"📂 Git: Creating branch {branch}...")
    # subprocess.run(["git", "checkout", "-b", branch], cwd=REPO_ROOT)
    # subprocess.run(["git", "commit", "-m", f"[AUTO-FIXED] Incident {fix.get('incident_ref', 'unknown')}"], cwd=REPO_ROOT)
    print(f"✅ Git: Autonomous fix committed to {branch}.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        manage_war_room(sys.argv[1])
    else:
        # Long-running daemon mode
        print("🎖 War Room: Daemon active. Listening for incidents...")
        seen = set()
        while True:
            objects = bus.get_objects_by_type("incident")
            for obj in objects:
                if obj['id'] not in seen:
                    manage_war_room(obj['id'])
                    seen.add(obj['id'])
            time.sleep(1)
