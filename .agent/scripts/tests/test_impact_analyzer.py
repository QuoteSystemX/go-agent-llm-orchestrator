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

import analysis.impact_analyzer as analyzer

class TestImpactAnalyzer(unittest.TestCase):
    @patch('subprocess.check_output')
    @patch('sys.stdout', new_callable=MagicMock)
    def test_analyze_impact_found(self, mock_stdout, mock_grep):
        mock_grep.return_value = b"file1.py\nfile2.go\n"
        
        analyzer.analyze_impact("refactor database")
        
        # Verify grep was called for keywords longer than 4
        # "refactor" (8) and "database" (8) should trigger grep
        self.assertEqual(mock_grep.call_count, 2)
        
        output = "".join(call[0][0] for call in mock_stdout.write.call_args_list)
        self.assertIn("Impact Analysis: 2 files potentially affected", output)
        self.assertIn("- file1.py", output)

    @patch('subprocess.check_output', side_effect=Exception("not found"))
    @patch('sys.stdout', new_callable=MagicMock)
    def test_analyze_impact_empty(self, mock_stdout, mock_grep):
        analyzer.analyze_impact("hi") # keyword too short
        output = "".join(call[0][0] for call in mock_stdout.write.call_args_list)
        self.assertIn("Impact Analysis: 0 files potentially affected", output)

if __name__ == "__main__":
    unittest.main()
