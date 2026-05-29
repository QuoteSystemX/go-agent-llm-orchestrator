import json
import time
from abc import ABC, abstractmethod
from pathlib import Path
from .paths import REPO_ROOT

BUS_DIR = REPO_ROOT / ".agent" / "bus"


class MetricCollector(ABC):
    """Base class for all metric collectors.

    Subclasses MUST implement run() to return a dict of collected metrics.
    For backward compatibility, subclasses that define collect() instead of
    run() are supported via a default run() → collect() delegation.
    """

    def __init__(self, name: str):
        self.name = name
        self.data = {
            "name": name,
            "timestamp": time.time(),
            "metrics": {},
            "status": "PASS",
        }

    def add_metric(self, key: str, value, status: str = "PASS"):
        self.data["metrics"][key] = {
            "value": value,
            "status": status,
        }
        if status != "PASS" and self.data["status"] == "PASS":
            self.data["status"] = status

    def save(self):
        BUS_DIR.mkdir(parents=True, exist_ok=True)
        file_path = BUS_DIR / f"{self.name.lower()}_metrics.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)
        return file_path

    @abstractmethod
    def run(self) -> dict:
        """Perform collection logic and return metrics dict.

        Must return at minimum {"status": "PASS" | "FAIL", "metrics": {...}}.
        Override this in subclasses. For backward compatibility, subclasses
        that define collect() instead of run() are supported automatically.
        """
        if hasattr(self, "collect") and callable(self.collect):
            return self.collect()
        raise NotImplementedError(
            f"{type(self).__name__} must implement run() or collect()"
        )
