#!/usr/bin/env python3
import unittest
import shutil
import sys
import os
import json
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

import dev.pr_audit as audit

class TestPRAudit(unittest.TestCase):
    @patch('subprocess.run')
    def test_run_check_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="success", stderr="")
        success, output = audit.run_check("Test", "echo 1")
        self.assertTrue(success)
        self.assertEqual(output, "success")

    @patch('subprocess.run')
    def test_run_check_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="out", stderr="err")
        success, output = audit.run_check("Test", "exit 1")
        self.assertFalse(success)
        self.assertIn("err", output)

    @patch('dev.pr_audit.run_check')
    @patch('sys.exit')
    def test_main_success(self, mock_exit, mock_check):
        mock_check.return_value = (True, "OK")
        with patch('sys.stdout', new=MagicMock()):
            audit.main()
        mock_exit.assert_called_with(0)

    @patch('dev.pr_audit.run_check')
    @patch('sys.exit')
    def test_main_failure(self, mock_exit, mock_check):
        mock_check.return_value = (False, "Error")
        with patch('sys.stdout', new=MagicMock()):
            audit.main()
        mock_exit.assert_called_with(1)

if __name__ == "__main__":
    unittest.main()
