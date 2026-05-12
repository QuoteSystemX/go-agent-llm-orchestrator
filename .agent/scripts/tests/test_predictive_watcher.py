#!/usr/bin/env python3
import unittest
from unittest.mock import patch, MagicMock
import json
import os
import shutil
from pathlib import Path
import sys

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev", "misc"]:
        sys.path.append(str(REPO_ROOT / ".agent" / "scripts" / domain))

import health.predictive_watcher; import sys; sys.modules['predictive_watcher'] = sys.modules['health.predictive_watcher']; import health.predictive_watcher as predictive_watcher

class TestPredictiveWatcher(unittest.TestCase):
    def setUp(self):
        self.test_root = REPO_ROOT / "scratch" / "test_predictive"
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        # Override REPO_ROOT and Path calls in predictive_watcher if needed
        # Actually, predictive_watcher uses Path(".") and Path(".agent/bus")
        # So we should run it in the test_root
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)

    def tearDown(self):
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    @patch("subprocess.check_output")
    def test_main_with_changes(self, mock_git):
        # Mock git status --porcelain
        mock_git.return_value = b"A  new_script.py\n?? untracked_dir/data.go\nM  modified.txt\n"
        
        predictive_watcher.main()
        
        # Check if reports are generated
        bus_outputs = Path(".agent/bus/outputs")
        self.assertTrue(bus_outputs.exists())
        predictions = list(bus_outputs.glob("prediction_*.json"))
        self.assertEqual(len(predictions), 1)
        
        with open(predictions[0]) as f:
            data = json.load(f)
            self.assertIn("new_script.py", data["impacted_files"])
            self.assertIn("untracked_dir/data.go", data["impacted_files"])
            self.assertNotIn("modified.txt", data["impacted_files"])

        foresight_report = Path(".agent/foresight/latest_risk_report.json")
        self.assertTrue(foresight_report.exists())
        with open(foresight_report) as f:
            risks = json.load(f)
            self.assertEqual(len(risks), 2)
            self.assertEqual(risks[0]["file"], "new_script.py")

    @patch("subprocess.check_output")
    def test_main_no_changes(self, mock_git):
        mock_git.return_value = b""
        
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            predictive_watcher.main()
        
        self.assertIn("✅ No major structural changes detected.", f.getvalue())

if __name__ == "__main__":
    unittest.main()
