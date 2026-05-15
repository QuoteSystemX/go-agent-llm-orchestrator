#!/usr/bin/env python3
import unittest
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

import analysis.resource_forecaster as forecaster

class TestResourceForecaster(unittest.TestCase):
    @patch('sys.stdout', new_callable=MagicMock)
    def test_forecast_resources_lean(self, mock_stdout):
        # 5 words * 1500 = 7500 tokens (well within 50k)
        self.assertTrue(forecaster.forecast_resources("build a small api endpoint"))
        output = "".join(call[0][0] for call in mock_stdout.write.call_args_list)
        self.assertIn("Predicted Tokens: 7,500", output)
        self.assertIn("Complexity Tier: Medium", output)
        self.assertIn("Budget pre-check passed", output)

    @patch('sys.stdout', new_callable=MagicMock)
    def test_forecast_resources_heavy_veto(self, mock_stdout):
        # 40 words * 1500 = 60,000 tokens (> 50k)
        long_intent = " ".join(["word"] * 40)
        self.assertFalse(forecaster.forecast_resources(long_intent))
        output = "".join(call[0][0] for call in mock_stdout.write.call_args_list)
        self.assertIn("BUDGET_EXCEEDED", output)
        self.assertIn("Predicted 60,000 > Max 50,000", output)
        self.assertIn("VETO. This is too expensive", output)

if __name__ == "__main__":
    unittest.main()
