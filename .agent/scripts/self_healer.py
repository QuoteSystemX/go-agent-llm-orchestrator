#!/usr/bin/env python3
"""Self-Healer — Autonomous Script Repair Wrapper.

Wraps command execution, catches errors, and generates repair plans using AI.
Part of the Unified Cardinal Enhancements Phase 2.
"""
import sys
import os
import subprocess
import traceback
from pathlib import Path

def run_with_healing(command):
    print(f"🔧 Running with Self-Healing: {' '.join(command)}")
    try:
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True
        )
        print(process.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Execution failed (Exit Code: {e.returncode})")
        print(f"🔍 Analyzing error...")
        
        error_msg = e.stderr or e.stdout
        print(f"--- ERROR ---\n{error_msg}\n-------------")
        
        # Identify the failing script
        script_path = None
        for arg in command:
            if arg.endswith(".py") and os.path.exists(arg):
                script_path = arg
                break
        
        if script_path:
            with open(script_path, "r") as f:
                source = f.read()
            
            # Generate Repair Prompt
            repair_prompt = f"""
### SELF-HEALING REPAIR REQUEST
The following script failed with an error. 

**Script Path**: {script_path}
**Error Output**:
{error_msg}

**Source Code**:
```python
{source}
```

Please provide a patch in standard diff format or the full corrected file content.
"""
            # In this ecosystem, we save the repair request to the bus
            bus_dir = Path(".agent/bus/outputs")
            bus_dir.mkdir(parents=True, exist_ok=True)
            
            import json
            from datetime import datetime
            
            repair_request = {
                "timestamp": datetime.now().isoformat(),
                "agent": "self-healer",
                "goal": f"Repair {script_path}",
                "status": "waiting_for_fix",
                "prompt": repair_prompt,
                "script_path": script_path,
                "error": error_msg
            }
            
            filename = f"repair_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(bus_dir / filename, "w") as f:
                json.dump(repair_request, f, indent=2)
            
            print(f"📝 Repair request saved to: .agent/bus/outputs/{filename}")
            print("🤖 Agent @debugger or @orchestrator should pick this up.")
            
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 self_healer.py <command>")
        sys.exit(1)
    
    success = run_with_healing(sys.argv[1:])
    sys.exit(0 if success else 1)
