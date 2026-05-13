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

import knowledge.archivist_trigger as trigger

class TestArchivistTrigger(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_archivist_trigger").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)

    def tearDown(self):
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    @patch('subprocess.run')
    def test_run_trigger(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="done", stderr="")
        
        result = trigger.run_trigger()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(result["results"]), len(trigger.SCRIPTS))
        self.assertEqual(result["results"][0]["stdout"], "done")

    @patch('subprocess.run')
    def test_run_trigger_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
        
        result = trigger.run_trigger()
        self.assertEqual(result["results"][0]["returncode"], 1)
        self.assertEqual(result["results"][0]["stderr"], "error")

if __name__ == "__main__":
    unittest.main()
