#!/usr/bin/env python3
"""Incident Watcher — The "Eyes" of the Auto-SRE.
Detects failed commands and triggers the War Room.
"""
import sys
import subprocess
import json
import time
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

def watch_command(cmd_args):
    """Executes a command and reports failure to the bus."""
    print(f"👁 Watcher: Executing '{' '.join(cmd_args)}'...")
    start_time = time.time()
    
    process = subprocess.Popen(
        cmd_args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=REPO_ROOT
    )
    
    stdout, stderr = process.communicate()
    duration = time.time() - start_time
    
    if process.returncode != 0:
        print(f"🚨 Watcher: Command FAILED (code {process.returncode}). Triggering War Room...")
        
        # Gather context
        incident_content = {
            "command": " ".join(cmd_args),
            "exit_code": process.returncode,
            "stdout": stdout[-2000:], 
            "stderr": stderr[-2000:],
            "duration": duration,
            "git_status": subprocess.getoutput("git status --short"),
            "severity": "high" if "test" in " ".join(cmd_args).lower() else "medium"
        }
        
        bus_manager.push(
            f"inc_{int(time.time())}",
            "incident", 
            "incident_watcher",
            json.dumps(incident_content)
        )
        print(f"✅ Incident pushed to bus.")
        
        # Output original error so user sees it too
        print(stderr, file=sys.stderr)
        return False
    
    print(f"✅ Watcher: Command succeeded in {duration:.2f}s.")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 incident_watcher.py <command> [args...]")
        sys.exit(1)
        
    success = watch_command(sys.argv[1:])
    sys.exit(0 if success else 1)
