#!/usr/bin/env python3
import unittest
import sys
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

import context.context_autofill as autofill

class TestContextAutofill(unittest.TestCase):
    @patch('subprocess.check_output')
    def test_search_codebase(self, mock_output):
        mock_output.return_value = b"./file_test.py\n./test_data.py"
        
        with patch('sys.stdout', new=MagicMock()):
            result = autofill.search_codebase("find the test files")
            
        self.assertIn("find", result)
        self.assertIn("test", result)
        self.assertIn("files", result)
        self.assertEqual(result["test"], ["./file_test.py", "./test_data.py"])

    @patch('context.context_autofill.search_codebase')
    @patch('sys.argv', ['context_autofill.py', 'intent', 'test'])
    def test_main(self, mock_search):
        mock_search.return_value = {"test": ["file.py"]}
        
        with patch('sys.stdout', new=MagicMock()):
            autofill.main()
            
        mock_search.assert_called_with("intent test")

    @patch('sys.argv', ['context_autofill.py'])
    def test_main_no_args(self):
        with self.assertRaises(SystemExit):
            with patch('sys.stdout', new=MagicMock()):
                autofill.main()

if __name__ == "__main__":
    unittest.main()
