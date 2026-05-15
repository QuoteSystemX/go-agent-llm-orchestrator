#!/usr/bin/env python3
import unittest
import sys
from unittest.mock import patch, MagicMock

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    import os
    from pathlib import Path
    REPO_ROOT = Path(__file__).resolve().parents[3]
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev", "misc"]:
        sys.path.append(str(REPO_ROOT / ".agent" / "scripts" / domain))

import analysis.truth_validator as validator

class TestTruthValidator(unittest.TestCase):
    @patch('sys.stdout', new_callable=MagicMock)
    def test_validate_truth_conflict(self, mock_stdout):
        res = validator.validate_truth("Implement auth system", [])
        self.assertTrue(res)
        output = "".join(call[0][0] for call in mock_stdout.write.call_args_list)
        self.assertIn("CONFLICT_OF_TRUTH", output)

    @patch('sys.stdout', new_callable=MagicMock)
    def test_validate_truth_no_conflict(self, mock_stdout):
        res = validator.validate_truth("Hello world", [])
        self.assertFalse(res)
        output = "".join(call[0][0] for call in mock_stdout.write.call_args_list)
        self.assertIn("No major contradictions", output)

if __name__ == "__main__":
    unittest.main()
