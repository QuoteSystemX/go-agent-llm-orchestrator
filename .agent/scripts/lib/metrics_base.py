import json
import time
from pathlib import Path
from .paths import REPO_ROOT

BUS_DIR = REPO_ROOT / ".agent" / "bus"

class MetricCollector:
    def __init__(self, name: str):
        self.name = name
        self.data = {
            "name": name,
            "timestamp": time.time(),
            "metrics": {},
            "status": "PASS"
        }

    def add_metric(self, key: str, value, status: str = "PASS"):
        self.data["metrics"][key] = {
            "value": value,
            "status": status
        }
        if status != "PASS" and self.data["status"] == "PASS":
            self.data["status"] = status

    def save(self):
        BUS_DIR.mkdir(parents=True, exist_ok=True)
        file_path = BUS_DIR / f"{self.name.lower()}_metrics.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)
        return file_path

    def run(self):
        """Override this method to perform collection logic."""
        raise NotImplementedError
