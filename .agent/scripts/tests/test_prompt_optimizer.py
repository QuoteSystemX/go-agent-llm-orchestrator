#!/usr/bin/env python3
import unittest
import json
import sys
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

import models.prompt_optimizer as prompt_optimizer

class TestPromptOptimizer(unittest.TestCase):
    @patch('models.prompt_optimizer.BUS_DIR', Path('/tmp/fake_bus'))
    @patch('models.prompt_optimizer.Path.exists')
    @patch('models.prompt_optimizer.load_json_safe')
    def test_analyze_telemetry(self, mock_load, mock_exists):
        mock_exists.return_value = True
        mock_load.return_value = {
            "objects": [
                {
                    "type": "telemetry",
                    "author": "coder",
                    "content": {"total_tokens": 60000}
                },
                {
                    "type": "telemetry",
                    "author": "coder",
                    "content": {"total_tokens": 40001}
                },
                {
                    "type": "telemetry",
                    "author": "analyst",
                    "content": {"total_tokens": 1000}
                }
            ]
        }
        
        report = prompt_optimizer.analyze_telemetry()
        
        self.assertIn("Agent: coder", report)
        self.assertIn("Total Tokens: 100001", report)
        self.assertIn("Average per call: 50000.5", report)
        self.assertIn("HIGH USAGE", report) # Average is 50k, should be >= 50k for warning
        
        self.assertIn("Agent: analyst", report)
        self.assertIn("EFFICIENT", report)

    @patch('models.prompt_optimizer.BUS_DIR', Path('/tmp/fake_bus'))
    @patch('models.prompt_optimizer.Path.exists', return_value=False)
    def test_analyze_telemetry_no_data(self, mock_exists):
        report = prompt_optimizer.analyze_telemetry()
        self.assertEqual(report, "No telemetry data found on the bus.")

if __name__ == "__main__":
    unittest.main()
