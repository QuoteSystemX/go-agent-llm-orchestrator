#!/usr/bin/env python3
"""
Blue Team Monitor - Operational Stability & Self-Healing
Checks health of MCP servers, system resources, and triggers recovery if needed.
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
import sys
import json
import psutil
import subprocess
from pathlib import Path
from datetime import datetime

# Paths
REPO_ROOT = Path(__file__).resolve().parents[3]
BUS_DIR = REPO_ROOT / ".agent" / "bus"
METRICS_FILE = BUS_DIR / "metrics_log.json"
PROVISIONER = REPO_ROOT / ".agent" / "scripts" / "health" / "mcp_provisioner.py"

def get_system_metrics():
    """Collect CPU, RAM, and Disk usage."""
    return {
        "cpu_percent": psutil.cpu_percent(interval=1),
        "ram_percent": psutil.virtual_memory().percent,
        "disk_free_gb": psutil.disk_usage('/').free / (1024**3)
    }

def check_mcp_server():
    """Check MCP server health using the provisioner."""
    try:
        result = subprocess.run(
            ["python3", str(PROVISIONER)],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT)
        )
        is_healthy = result.returncode == 0
        return is_healthy, result.stdout.strip()
    except Exception as e:
        return False, str(e)

def log_metrics(metrics, status):
    """Log metrics to the Context Bus."""
    BUS_DIR.mkdir(parents=True, exist_ok=True)
    
    log_entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "system": metrics,
        "mcp_status": status
    }
    
    # Maintain a rolling log of last 100 entries
    history = []
    if METRICS_FILE.exists():
        try:
            with open(METRICS_FILE, 'r') as f:
                history = json.load(f)
        except:
            history = []
            
    history.append(log_entry)
    history = history[-100:]
    
    with open(METRICS_FILE, 'w') as f:
        json.dump(history, f, indent=2)

def read_previous_status() -> str:
    """Read the last written stability status, default to HEALTHY."""
    status_file = BUS_DIR / "blue_team_status.json"
    if status_file.exists():
        try:
            return json.loads(status_file.read_text()).get("status", "HEALTHY")
        except Exception:
            pass
    return "HEALTHY"

def main() -> None:
    print(f"\n{'='*60}")
    print(f"🔵 BLUE TEAM MONITOR - Stability Check")
    print(f"{'='*60}")

    # 1. System Check
    metrics = get_system_metrics()
    print(f"🖥  System: CPU {metrics['cpu_percent']}% | RAM {metrics['ram_percent']}% | Disk {metrics['disk_free_gb']:.1f}GB free")

    # 2. MCP Check
    is_healthy, msg = check_mcp_server()

    # 3. State machine: prev_status → new_status
    prev_status = read_previous_status()
    if is_healthy:
        status = "HEALTHY"  # always recover to HEALTHY when MCP is up
        print(f"✅ MCP Server: {msg}")
        if prev_status in ("DOWN", "RECOVERING"):
            print(f"✅ Recovered from {prev_status}")
    else:
        print(f"⚠️  MCP Server: {msg}")
        if prev_status == "HEALTHY":
            # First failure — enter RECOVERING
            status = "RECOVERING"
            print("🛠  Triggering Self-Healing (HEALTHY → RECOVERING)")
        else:
            # Still down — stay RECOVERING until resolved
            status = "RECOVERING"
            print(f"🔄 Still recovering (prev: {prev_status})")

    # 4. Log results
    log_metrics(metrics, status)

    # 5. Write status for status_report
    with open(BUS_DIR / "blue_team_status.json", "w") as f:
        json.dump({
            "status": status,
            "system_health": "OK" if metrics['cpu_percent'] < 90 else "HIGH_LOAD",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }, f, indent=2)

if __name__ == "__main__":
    main()
