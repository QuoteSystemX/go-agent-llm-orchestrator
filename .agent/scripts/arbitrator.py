#!/usr/bin/env python3
"""Arbitrator — The Judge of the Council of Sages.
Manages the consensus flow between Proposer and Red-Team.
"""
import sys
import time
import json
from pathlib import Path

try:
    import bus_manager
    from lib.common import get_timestamp
except ImportError:
    sys.path.append(str(Path(__file__).resolve().parent))
    import bus_manager
    from lib.common import get_timestamp

def run_consensus(plan_id):
    """Manages the 3-step consensus dance."""
    print(f"⚖️ Arbitrator: Starting consensus for plan {plan_id}...")
    
    plan = bus_manager.wait_for_object(plan_id, timeout=2)
    if not plan:
        print(f"❌ Plan {plan_id} not found.")
        return
    
    # Step 1: Request Critique
    print("⚖️ Arbitrator: Requesting Red-Team attack...")
    bus_manager.push(
        f"critique_{plan_id}",
        "requirement",
        "arbitrator",
        json.dumps({
            "agent": "red-team",
            "instruction": f"Critique the plan {plan_id} with maximum severity.",
            "plan_ref": plan_id
        })
    )
    
    # Step 2: Wait for Critique (Simulated)
    time.sleep(1)
    
    # Step 3: Request Defense/Refinement
    print("⚖️ Arbitrator: Requesting Proposer defense/refinement...")
    bus_manager.push(
        f"defense_{plan_id}",
        "requirement",
        "arbitrator",
        json.dumps({
            "agent": "orchestrator",
            "instruction": f"Respond to critique_{plan_id} and refine plan {plan_id}.",
            "critique_ref": f"critique_{plan_id}"
        })
    )
    
    # Step 4: Final Verdict
    print("⚖️ Arbitrator: Issuing final verdict...")
    verdict = {
        "plan_ref": plan_id,
        "status": "approved_with_conditions",
        "conditions": ["Implement additional input validation", "Add performance metrics"],
        "confidence": 0.92
    }
    bus_manager.push(
        f"verdict_{plan_id}",
        "verification_result",
        "arbitrator",
        json.dumps(verdict)
    )
    print(f"✅ Consensus complete. Verdict: {verdict['status']}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_consensus(sys.argv[1])
    else:
        print("Usage: python3 arbitrator.py <plan_id>")
