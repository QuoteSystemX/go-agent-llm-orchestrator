#!/usr/bin/env python3
import unittest
import shutil
import sys
import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev", "misc"]:
        sys.path.append(str(REPO_ROOT / ".agent" / "scripts" / domain))

import analysis.intelligence_roi_collector as roi

class TestROICollector(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_roi").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.telemetry_path = self.test_root / "telemetry.json"
        self.config_path = self.test_root / ".agent" / "config" / "router_rules.json"
        self.config_path.parent.mkdir(parents=True)
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)
        
        # Patch paths directly in the target module and lib.paths
        self.patch_telemetry = patch('analysis.intelligence_roi_collector.TELEMETRY_PATH', self.telemetry_path)
        self.patch_root_target = patch('analysis.intelligence_roi_collector.REPO_ROOT', self.test_root)
        self.patch_root_lib = patch('lib.paths.REPO_ROOT', self.test_root)
        
        self.patch_telemetry.start()
        self.patch_root_target.start()
        self.patch_root_lib.start()

    def tearDown(self):
        self.patch_telemetry.stop()
        self.patch_root_target.stop()
        self.patch_root_lib.stop()
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_roi_calculation_local_dominant(self):
        # Local models
        self.config_path.write_text(json.dumps({
            "models": {"ollama": {"L1": "qwen2.5"}}
        }))
        
        self.telemetry_path.write_text(json.dumps({
            "events": [
                {"model_id": "qwen2.5", "score": 10},
                {"model_id": "gpt-4", "score": 15},
                {"model_id": "qwen2.5", "score": 10}
            ]
        }))
        
        collector = roi.IntelligenceROICollector()
        collector.run()
        
        metrics = collector.data["metrics"]
        # Metrics: total_calls, local_calls, cloud_calls, local_ratio, avg_complexity, efficiency_score
        self.assertEqual(metrics["total_calls"]["value"], 3)
        self.assertEqual(metrics["local_calls"]["value"], 2) # qwen is local
        self.assertEqual(metrics["cloud_calls"]["value"], 1) # gpt-4 is cloud
        self.assertIn("66.7%", metrics["local_ratio"]["value"])
        self.assertEqual(metrics["efficiency_score"]["status"], "PASS")

    def test_roi_calculation_cloud_dominant(self):
        self.telemetry_path.write_text(json.dumps({
            "events": [
                {"model_id": "claude-3", "score": 10},
                {"model_id": "gpt-4", "score": 15}
            ]
        }))
        
        collector = roi.IntelligenceROICollector()
        collector.run()
        
        metrics = collector.data["metrics"]
        self.assertEqual(metrics["cloud_calls"]["value"], 2)
        self.assertIn("0.0%", metrics["local_ratio"]["value"])
        self.assertEqual(metrics["efficiency_score"]["status"], "WARN")

    def test_no_data(self):
        collector = roi.IntelligenceROICollector()
        collector.run()
        self.assertEqual(collector.data["metrics"]["roi"]["value"], "No Data")

if __name__ == "__main__":
    unittest.main()
