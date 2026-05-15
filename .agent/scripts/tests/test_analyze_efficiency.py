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

import analysis.analyze_efficiency as eff

class TestAnalyzeEfficiency(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_efficiency").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        self.logs_dir = self.test_root / ".agent" / "logs"
        self.logs_dir.mkdir(parents=True)
        self.metrics_file = self.logs_dir / "metrics.jsonl"
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)
        
        # Patch paths
        self.patch_root = patch('analysis.analyze_efficiency.REPO_ROOT', self.test_root)
        self.patch_file = patch('analysis.analyze_efficiency.METRICS_FILE', self.metrics_file)
        self.patch_root.start()
        self.patch_file.start()

    def tearDown(self):
        self.patch_root.stop()
        self.patch_file.stop()
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    @patch('sys.stdout', new_callable=MagicMock)
    def test_analyze_success(self, mock_stdout):
        # Create sample metrics
        metrics = [
            {"agent": "coder", "metric": "prompt_tokens", "value": 1000, "status": "success"},
            {"agent": "coder", "metric": "completion_tokens", "value": 500, "status": "success"},
            {"agent": "coder", "metric": "latency_ms", "value": 2000, "status": "success"},
            {"agent": "coder", "metric": "status", "value": "success"},
            {"agent": "reviewer", "metric": "prompt_tokens", "value": 500, "status": "error"},
            {"agent": "reviewer", "metric": "status", "value": "error"},
        ]
        with open(self.metrics_file, "w") as f:
            for m in metrics:
                f.write(json.dumps(m) + "\n")
        
        eff.analyze()
        
        output = "".join(call[0][0] for call in mock_stdout.write.call_args_list)
        self.assertIn("## Agent: `coder`", output)
        self.assertIn("**Total Tokens**: 1,500", output)
        self.assertIn("**Success Rate**: 100.0%", output)
        self.assertIn("## Agent: `reviewer`", output)
        self.assertIn("**Success Rate**: 0.0%", output)
        self.assertIn("High error rate", output)

    @patch('sys.stdout', new_callable=MagicMock)
    def test_analyze_recommendations(self, mock_stdout):
        # High tokens and latency
        metrics = [
            {"agent": "heavy", "metric": "prompt_tokens", "value": 60000, "status": "success"},
            {"agent": "heavy", "metric": "latency_ms", "value": 15000, "status": "success"},
            {"agent": "heavy", "metric": "status", "value": "success"},
        ]
        with open(self.metrics_file, "w") as f:
            for m in metrics:
                f.write(json.dumps(m) + "\n")
        
        eff.analyze()
        
        output = "".join(call[0][0] for call in mock_stdout.write.call_args_list)
        self.assertIn("High token usage", output)
        self.assertIn("High latency", output)

    @patch('sys.stdout', new_callable=MagicMock)
    def test_analyze_empty(self, mock_stdout):
        eff.analyze()
        output = "".join(call[0][0] for call in mock_stdout.write.call_args_list)
        self.assertIn("No metrics to analyze", output)

if __name__ == "__main__":
    unittest.main()
