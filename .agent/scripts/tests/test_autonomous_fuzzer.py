#!/usr/bin/env python3
import unittest
import sys
import os
import shutil
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

import chaos.autonomous_fuzzer as fuzzer

class TestAutonomousFuzzer(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_fuzzer").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)

    def tearDown(self):
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    @patch('sys.stdout', new_callable=MagicMock)
    def test_run_fuzz_with_targets(self, mock_stdout):
        results = fuzzer.run_fuzz(target="os.path.join", payloads=["", "../etc/passwd"], tag="test")
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)

    @patch('sys.stdout', new_callable=MagicMock)
    def test_run_fuzz_no_targets(self, mock_stdout):
        # run_fuzz requires target/payloads; empty payloads = no tests
        results = fuzzer.run_fuzz(target="nonexistent.func", payloads=[], tag="empty")
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 0)

if __name__ == "__main__":
    unittest.main()
