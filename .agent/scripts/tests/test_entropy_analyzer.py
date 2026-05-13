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

import context.entropy_analyzer as entropy

class TestEntropyAnalyzer(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_entropy").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)

    def tearDown(self):
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_get_file_complexity(self):
        f = self.test_root / "complex.py"
        # 4 lines, max indent 12
        f.write_text("def a():\n    if b:\n        while c:\n            pass")
        
        complexity = entropy.get_file_complexity(f)
        # (4 * 0.1) + (12 * 0.5) = 0.4 + 6.0 = 6.4
        self.assertAlmostEqual(complexity, 6.4)

    @patch('context.entropy_analyzer.get_churn_metrics')
    @patch('sys.stdout', new_callable=MagicMock)
    def test_run_foresight_analysis(self, mock_stdout, mock_churn):
        # Setup files
        (self.test_root / "risky.py").write_text("def big():\n" + "    pass\n" * 100)
        
        mock_churn.return_value = {"risky.py": 50}
        
        entropy.run_foresight_analysis(repo_root=self.test_root)
        
        report_file = self.test_root / ".agent" / "foresight" / "latest_risk_report.json"
        self.assertTrue(report_file.exists())
        
        report = json.loads(report_file.read_text())
        self.assertTrue(any(r["file"] == "risky.py" for r in report))
        self.assertTrue(report[0]["risk_score"] > 20)

if __name__ == "__main__":
    unittest.main()
