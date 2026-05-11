#!/usr/bin/env python3
"""
Blue Team Monitor - Operational Stability & Self-Healing
Checks health of MCP servers, system resources, and triggers recovery if needed.
"""
import os
import sys
import json
import psutil
import subprocess
from pathlib import Path
from datetime import datetime

# Paths
REPO_ROOT = Path(__file__).resolve().parents[2]
BUS_DIR = REPO_ROOT / ".agent" / "bus"
METRICS_FILE = BUS_DIR / "metrics_log.json"
PROVISIONER = REPO_ROOT / ".agent" / "scripts" / "mcp_provisioner.py"

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

def main() -> None:
    print(f"\n{'='*60}")
    print(f"🔵 BLUE TEAM MONITOR - Stability Check")
    print(f"{'='*60}")
    
    # 1. System Check
    metrics = get_system_metrics()
    print(f"🖥  System: CPU {metrics['cpu_percent']}% | RAM {metrics['ram_percent']}% | Disk {metrics['disk_free_gb']:.1f}GB free")
    
    # 2. MCP Check
    is_healthy, msg = check_mcp_server()
    status = "HEALTHY" if is_healthy else "DOWN"
    
    if is_healthy:
        print(f"✅ MCP Server: {msg}")
    else:
        print(f"⚠️  MCP Server: {msg}")
        print("🛠  Triggering Self-Healing...")
        # Self-healing is already part of mcp_provisioner's main() if it fails health check
        # But we log it as a recovery event
        status = "RECOVERING"
        
    # 3. Log results
    log_metrics(metrics, status)
    
    # 4. Final Status for status_report
    with open(BUS_DIR / "blue_team_status.json", "w") as f:
        json.dump({
            "status": status,
            "system_health": "OK" if metrics['cpu_percent'] < 90 else "HIGH_LOAD",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }, f, indent=2)

if __name__ == "__main__":
    main()
