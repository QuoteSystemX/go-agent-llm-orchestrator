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

    def test_calculate_file_risk(self):
        # Create a mock core file with 15 lines
        lib_dir = Path("lib")
        lib_dir.mkdir()
        mock_file = lib_dir / "core_file.py"
        mock_file.write_text("\n".join(f"line {i}" for i in range(15)))
        
        # Test risk calculation
        risk = predictive_watcher.calculate_file_risk(str(mock_file))
        # Expected: 10 (base) + 15 (diff_score) + 0 (ref_score) + 20 (core_bonus) = 45
        self.assertEqual(risk, 45)

    @patch("subprocess.run")
    def test_calculate_file_risk_with_git(self, mock_run):
        mock_diff = MagicMock()
        mock_diff.stdout = "25\t5\tlib/core_file.py"
        
        mock_grep = MagicMock()
        mock_grep.stdout = "file1.py:import core_file\nfile2.py:import core_file\n"
        
        mock_run.side_effect = [mock_diff, mock_grep]
        
        lib_dir = Path("lib")
        lib_dir.mkdir(exist_ok=True)
        mock_file = lib_dir / "core_file.py"
        mock_file.write_text("dummy")
        
        risk = predictive_watcher.calculate_file_risk(str(mock_file))
        # Expected: 10 (base) + 30 (diff) + 10 (ref) + 20 (core) = 70
        self.assertEqual(risk, 70)

if __name__ == "__main__":
    unittest.main()
