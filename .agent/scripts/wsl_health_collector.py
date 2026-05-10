#!/usr/bin/env python3
import os
import platform
import subprocess
import sys
from pathlib import Path

# Antigravity Standard: Path Resolution
sys.path.append(str(Path(__file__).resolve().parent))
from lib.metrics_base import MetricCollector
from lib.common import discover_ollama_url

class WSLHealthCollector(MetricCollector):
    """
    Collects health metrics specific to WSL2 environment.
    Checks kernel version, Windows host connectivity, and mount points.
    """
    def __init__(self):
        super().__init__("WSL_Health")

    def collect(self):
        is_wsl = False
        kernel_version = platform.release()
        
        # 1. Detect WSL2
        try:
            if os.path.exists("/proc/version"):
                with open("/proc/version", "r") as f:
                    version_info = f.read().lower()
                    is_wsl = "microsoft" in version_info
        except Exception:
            pass

        if not is_wsl:
            # We skip if not in WSL to avoid polluting metrics in other environments
            return

        # 2. Check Gateway (Windows Host)
        ollama_url = discover_ollama_url()
        # discover_ollama_url returns something like "http://172.31.0.1:11434"
        gateway_ip = "Unknown"
        if ollama_url and "//" in ollama_url:
            try:
                gateway_ip = ollama_url.split("//")[1].split(":")[0]
            except IndexError:
                pass
        
        gw_status = "DOWN"
        if gateway_ip != "Unknown" and gateway_ip != "localhost" and gateway_ip != "127.0.0.1":
            try:
                # Ping gateway (1 attempt, 1s timeout)
                res = subprocess.run(["ping", "-c", "1", "-W", "1", gateway_ip], capture_output=True, text=True)
                if res.returncode == 0:
                    gw_status = "UP"
            except Exception:
                pass
        else:
            # If it's localhost, we consider it UP for this metric's purpose (it's reachable)
            gw_status = "LOCAL"

        # 3. Check Mounts (Common indicator of WSL health)
        has_mnt_c = os.path.exists("/mnt/c")

        # 4. Populate Metrics
        self.add_metric("kernel", kernel_version, "PASS")
        self.add_metric("gateway_ip", gateway_ip, "PASS")
        self.add_metric("host_connectivity", gw_status, "PASS" if gw_status in ["UP", "LOCAL"] else "WARN")
        self.add_metric("mount_c", "AVAILABLE" if has_mnt_c else "MISSING", "PASS" if has_mnt_c else "WARN")
        
        # Overall status
        if gw_status == "DOWN":
            self.status = "WARN"
        elif not has_mnt_c:
            self.status = "WARN"
        else:
            self.status = "PASS"
            
        self.save()
        print(f"✅ WSL Health metrics collected. Status: {self.status}")

if __name__ == "__main__":
    WSLHealthCollector().collect()
