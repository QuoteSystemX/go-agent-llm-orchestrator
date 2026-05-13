#!/usr/bin/env python3
import unittest
import shutil
import sys
import json
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

import dev.linter_debt_collector as ldc

class TestLinterDebtCollector(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_linter_debt").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.metrics_dir = self.test_root / ".agent" / "bus"
        self.metrics_dir.mkdir(parents=True)
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)
        
        # Patch paths
        self.patch_root = patch('dev.linter_debt_collector.REPO_ROOT', self.test_root)
        self.patch_root.start()

    def tearDown(self):
        self.patch_root.stop()
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_run_debt_calculation(self):
        # Create code files
        f1 = self.test_root / "clean.py"
        f1.write_text("print('hello')")
        
        f2 = self.test_root / "dirty.py"
        f2.write_text("x = 1 # noqa\ny = 2 # nolint")
        
        f3 = self.test_root / "js_debt.js"
        f3.write_text("// eslint-disable-next-line\nconsole.log(x)")
        
        collector = ldc.LinterDebtCollector()
        collector.save = MagicMock()
        
        collector.run()
        
        # 2 out of 3 files have debt = 66.7%
        # Instances: 1 (noqa) + 1 (nolint) + 1 (eslint-disable) = 3
        metrics = collector.data["metrics"]
        self.assertEqual(metrics["total_files"]["value"], 3)
        self.assertEqual(metrics["files_with_debt"]["value"], 2)
        self.assertEqual(metrics["total_instances"]["value"], 3)
        self.assertEqual(metrics["debt_index"]["value"], "66.7%")
        self.assertEqual(metrics["debt_index"]["status"], "FAIL")

    def test_no_files(self):
        collector = ldc.LinterDebtCollector()
        collector.save = MagicMock()
        collector.run()
        self.assertEqual(collector.data["metrics"]["debt_index"]["value"], "0.0%")

if __name__ == "__main__":
    unittest.main()
