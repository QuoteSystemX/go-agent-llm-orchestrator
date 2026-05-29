#!/usr/bin/env python3
import unittest
import shutil
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

import dev.ci_auto_fixer as fixer

class TestCIAutoFixer(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_ci_fixer").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        (self.test_root / "tasks").mkdir()
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)

    def tearDown(self):
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    @patch('dev.ci_auto_fixer._run_lint', return_value=[
        {'file': 'test.py', 'line': 1, 'col': 1, 'code': 'F401', 'message': 'module imported but unused'}
    ])
    @patch('dev.ci_auto_fixer._apply_auto_fix', return_value=False)
    def test_run_auto_fix(self, mock_fix, mock_lint):
        fixer.run_auto_fix()
        
        task_file = Path("tasks/ci-auto-fix-needed.md")
        self.assertTrue(task_file.exists())
        content = task_file.read_text()
        self.assertIn("[BUG] Autonomous Fix", content)

if __name__ == "__main__":
    unittest.main()
