import subprocess
import json
import re
from lib.metrics_base import MetricCollector
from lib.paths import REPO_ROOT

class SyncParityCollector(MetricCollector):
    def __init__(self):
        super().__init__("Sync_Parity")
        self.sync_script = REPO_ROOT / ".agent" / "scripts" / "sync_agents.py"

    def run(self):
        from sync_agents import TARGETS
        
        overall_status = "PASS"
        drift_details = {}

        for target in TARGETS:
            res = subprocess.run(
                ["python3", str(self.sync_script), "--target", target, "--check"],
                capture_output=True, text=True
            )
            
            if res.returncode == 0:
                drift_details[target] = {"status": "OK", "issues": []}
            else:
                # Parse output for missing/stale files
                issues = []
                # Simple regex to find paths in the error output
                # Assuming sync_agents.py prints something like "Missing: path/to/file"
                for line in res.stdout.splitlines():
                    if "Missing:" in line or "Stale:" in line or "Drift:" in line:
                        issues.append(line.strip())
                
                drift_details[target] = {"status": "DRIFT", "issues": issues}
                overall_status = "WARN"

        self.add_metric("targets", drift_details, overall_status)
        self.save()
        print(f"✅ Sync Parity details saved (Status: {overall_status})")

if __name__ == "__main__":
    SyncParityCollector().run()
