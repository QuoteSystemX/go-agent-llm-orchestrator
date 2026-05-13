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

import knowledge.ki_coverage_collector as ki

class TestKICoverageCollector(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_ki_coverage").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.metrics_dir = self.test_root / ".agent" / "metrics"
        self.metrics_dir.mkdir(parents=True)
        
        self.ki_dir = self.test_root / ".agent" / "knowledge"
        self.ki_dir.mkdir(parents=True)
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)
        
        # Patch paths
        self.patch_root = patch('knowledge.ki_coverage_collector.REPO_ROOT', self.test_root)
        self.patch_root.start()

    def tearDown(self):
        self.patch_root.stop()
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_run_coverage_logic(self):
        # Create code files
        (self.test_root / "src").mkdir()
        f1 = self.test_root / "src" / "covered.py"
        f1.write_text("# covered")
        f2 = self.test_root / "src" / "uncovered.py"
        f2.write_text("# uncovered")
        
        # Create KI mentioning f1
        (self.ki_dir / "Rules.md").write_text(f"This covers {f1.relative_to(self.test_root)}")
        
        collector = ki.KICoverageCollector()
        # Mock MetricCollector.save to prevent writing to real bus
        collector.save = MagicMock()
        
        collector.run()
        
        # 1 out of 2 files covered = 50%
        metrics = collector.data["metrics"]
        self.assertEqual(metrics["total_files"]["value"], 2)
        self.assertEqual(metrics["covered_files"]["value"], 1)
        self.assertEqual(metrics["coverage_pct"]["value"], "50.0%")
        self.assertEqual(metrics["coverage_pct"]["status"], "WARN")

    def test_no_files(self):
        collector = ki.KICoverageCollector()
        collector.save = MagicMock()
        collector.run()
        self.assertEqual(collector.data["metrics"]["coverage"]["value"], 0)

if __name__ == "__main__":
    unittest.main()
