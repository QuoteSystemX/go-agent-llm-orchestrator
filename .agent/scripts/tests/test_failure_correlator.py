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

import misc.failure_correlator as correlator

class TestFailureCorrelator(unittest.TestCase):
    @patch('sys.stdout', new_callable=MagicMock)
    def test_correlate_failures_match(self, mock_stdout):
        correlator.correlate_failures("implement cache logic")
        output = "".join(call[0][0] for call in mock_stdout.write.call_args_list)
        self.assertIn("HISTORICAL MATCH", output)
        self.assertIn("Recommendation: Use atomic operations", output)

    @patch('sys.stdout', new_callable=MagicMock)
    def test_correlate_failures_no_match(self, mock_stdout):
        correlator.correlate_failures("say hello")
        output = "".join(call[0][0] for call in mock_stdout.write.call_args_list)
        self.assertIn("No relevant historical failures found", output)

if __name__ == "__main__":
    unittest.main()
