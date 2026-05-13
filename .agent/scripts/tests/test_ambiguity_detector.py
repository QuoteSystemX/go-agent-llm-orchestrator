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

import analysis.ambiguity_detector as detector

class TestAmbiguityDetector(unittest.TestCase):
    @patch('sys.stdout', new_callable=MagicMock)
    def test_check_ambiguity_too_short(self, mock_stdout):
        self.assertFalse(detector.check_ambiguity("Fix bug"))
        output = "".join(call[0][0] for call in mock_stdout.write.call_args_list)
        self.assertIn("CRITICAL AMBIGUITY", output)

    @patch('sys.stdout', new_callable=MagicMock)
    def test_check_ambiguity_vague(self, mock_stdout):
        # 3 out of 5 words are vague (60% > 50%)
        self.assertFalse(detector.check_ambiguity("Make it improve something beautifully"))
        output = "".join(call[0][0] for call in mock_stdout.write.call_args_list)
        self.assertIn("HIGH AMBIGUITY", output)

    @patch('sys.stdout', new_callable=MagicMock)
    def test_check_ambiguity_clear(self, mock_stdout):
        self.assertTrue(detector.check_ambiguity("Refactor the user authentication logic in auth.py"))
        output = "".join(call[0][0] for call in mock_stdout.write.call_args_list)
        self.assertIn("Prompt clarity is acceptable", output)

if __name__ == "__main__":
    unittest.main()
