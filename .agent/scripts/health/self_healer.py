#!/usr/bin/env python3
"""Self-Healer — Autonomous Script Repair Wrapper.

Wraps command execution, catches errors, and generates repair plans using AI.
Part of the Unified Cardinal Enhancements Phase 2.
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
        
        # Pattern Recognition
        if "ModuleNotFoundError" in error_msg:
            parts = error_msg.split("'")
            if len(parts) >= 2:
                missing_module = parts[-2]
                print(f"💡 Detected missing module: {missing_module}")
                # Try to find it in the repo (common Antigravity issue)
                found = list(Path(".agent/scripts").rglob(f"{missing_module}.py"))
                if found:
                    print(f"✅ Found module in repo: {found[0]}. Suggesting PYTHONPATH update.")
                else:
                    print(f"🛠  Suggesting installation: pip install {missing_module}")
            else:
                print("💡 Could not identify missing module name.")

        if "Permission denied" in error_msg:
            print("🛡️ Attempting auto-fix: Setting +x permissions...")
            for arg in command:
                if os.path.exists(arg):
                    os.chmod(arg, os.stat(arg).st_mode | 0o111)

        if script_path:
            with open(script_path, "r") as f:
                source = f.read()
            
            # Enrich context with recent logs
            logs = ""
            log_path = Path(".agent/logs/orchestration.log")
            if log_path.exists():
                with open(log_path, "r") as f:
                    logs = "".join(f.readlines()[-20:])

            # Generate Repair Prompt
            repair_prompt = f"""
### SELF-HEALING REPAIR REQUEST
**Script Path**: {script_path}
**Error Output**:
{error_msg}

**Context (Recent Logs)**:
{logs}

**Source Code**:
```python
{source}
```
"""
            # Save to bus
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
                "error": error_msg,
                "type": "Runtime Failure"
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
