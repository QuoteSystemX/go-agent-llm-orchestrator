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

import dev.test_runner as test_runner

class TestTestRunner(unittest.TestCase):
    @patch('unittest.TestLoader')
    @patch('unittest.TextTestRunner')
    def test_run_all_tests_success(self, mock_runner_class, mock_loader_class):
        mock_runner = MagicMock()
        mock_result = MagicMock()
        mock_result.wasSuccessful.return_value = True
        mock_runner.run.return_value = mock_result
        mock_runner_class.return_value = mock_runner
        
        mock_loader = MagicMock()
        mock_suite = MagicMock()
        mock_loader.discover.return_value = mock_suite
        mock_loader_class.return_value = mock_loader
        
        # We need to mock test_dir.exists() to True
        with patch('pathlib.Path.exists', return_value=True):
            with patch('sys.stdout', new=MagicMock()):
                test_runner.run_all_tests()
                
        mock_runner.run.assert_called_once_with(mock_suite)

    @patch('unittest.TestLoader')
    @patch('unittest.TextTestRunner')
    def test_run_all_tests_failure(self, mock_runner_class, mock_loader_class):
        mock_runner = MagicMock()
        mock_result = MagicMock()
        mock_result.wasSuccessful.return_value = False
        mock_runner.run.return_value = mock_result
        mock_runner_class.return_value = mock_runner
        
        with patch('pathlib.Path.exists', return_value=True):
            with patch('sys.stdout', new=MagicMock()):
                with self.assertRaises(SystemExit) as cm:
                    test_runner.run_all_tests()
                self.assertEqual(cm.exception.code, 1)

    def test_run_all_tests_no_dir(self):
        with patch('pathlib.Path.exists', return_value=False):
            with patch('sys.stdout', new=MagicMock()):
                with self.assertRaises(SystemExit) as cm:
                    test_runner.run_all_tests()
                self.assertEqual(cm.exception.code, 1)

if __name__ == "__main__":
    unittest.main()
