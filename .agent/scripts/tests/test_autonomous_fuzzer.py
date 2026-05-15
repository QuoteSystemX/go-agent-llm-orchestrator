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
        # Create a target package
        (self.test_root / "pkg").mkdir()
        
        fuzzer.run_fuzz()
        
        output = "".join(call[0][0] for call in mock_stdout.write.call_args_list)
        self.assertIn("Fuzzing targets: ['pkg']", output)
        self.assertIn("Stress testing: pkg", output)

    @patch('sys.stdout', new_callable=MagicMock)
    def test_run_fuzz_no_targets(self, mock_stdout):
        fuzzer.run_fuzz()
        
        output = "".join(call[0][0] for call in mock_stdout.write.call_args_list)
        self.assertIn("No target packages found", output)
        self.assertIn(".agent/scripts", output)

if __name__ == "__main__":
    unittest.main()
