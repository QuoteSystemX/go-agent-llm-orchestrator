#!/usr/bin/env python3
import unittest
import os
import shutil
import json
from pathlib import Path
import sys

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev", "misc"]:
        sys.path.append(str(REPO_ROOT / ".agent" / "scripts" / domain))

import lib.paths
import lib.metrics_base
import analysis.intelligence_roi_collector; import sys; sys.modules['intelligence_roi_collector'] = sys.modules['analysis.intelligence_roi_collector']; import analysis.intelligence_roi_collector as intelligence_roi_collector

class TestROICollector(unittest.TestCase):
    def setUp(self):
        self.test_root = REPO_ROOT / "scratch" / "test_roi"
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        # Override paths in the libraries
        self.original_root = lib.paths.REPO_ROOT
        self.original_telemetry = lib.paths.TELEMETRY_PATH
        self.original_bus = lib.metrics_base.BUS_DIR
        
        lib.paths.REPO_ROOT = self.test_root
        lib.paths.TELEMETRY_PATH = self.test_root / ".agent" / "data" / "telemetry.json"
        lib.metrics_base.REPO_ROOT = self.test_root
        lib.metrics_base.BUS_DIR = self.test_root / ".agent" / "bus"
        intelligence_roi_collector.REPO_ROOT = self.test_root
        intelligence_roi_collector.TELEMETRY_PATH = lib.paths.TELEMETRY_PATH
        
        # Mock telemetry
        os.makedirs(intelligence_roi_collector.TELEMETRY_PATH.parent, exist_ok=True)
        telemetry = {
            "events": [
                {"model_id": "qwen2.5-coder:32b", "score": 15},
                {"model_id": "claude-3-opus", "score": 18},
                {"model_id": "deepseek-r1", "score": 12}
            ]
        }
        with open(intelligence_roi_collector.TELEMETRY_PATH, "w") as f:
            json.dump(telemetry, f)

    def tearDown(self):
        lib.paths.REPO_ROOT = self.original_root
        lib.paths.TELEMETRY_PATH = self.original_telemetry
        lib.metrics_base.BUS_DIR = self.original_bus
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_run(self):
        collector = intelligence_roi_collector.IntelligenceROICollector()
        collector.run()
        
        metrics_file = self.test_root / ".agent" / "bus" / "intelligence_roi_metrics.json"
        self.assertTrue(metrics_file.exists())
        
        with open(metrics_file) as f:
            data = json.load(f)
            # 2 local (qwen, deepseek), 1 cloud (claude)
            self.assertEqual(data["metrics"]["local_calls"]["value"], 2)
            self.assertEqual(data["metrics"]["cloud_calls"]["value"], 1)
            self.assertEqual(data["metrics"]["local_ratio"]["value"], "66.7%")

if __name__ == "__main__":
    unittest.main()
