#!/usr/bin/env python3
import unittest
import shutil
import sys
import json
import os
import subprocess
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

import health.self_healer as healer

class TestSelfHealer(unittest.TestCase):
    def setUp(self):
        self.test_root = REPO_ROOT / "scratch" / "test_healer"
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        # Setup mock .agent/bus/outputs
        (self.test_root / ".agent" / "bus" / "outputs").mkdir(parents=True)
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)

    def tearDown(self):
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    @patch('subprocess.run')
    def test_run_success(self, mock_run):
        mock_proc = MagicMock()
        mock_proc.stdout = "Success Output"
        mock_run.return_value = mock_proc
        
        success = healer.run_with_healing(["ls"])
        self.assertTrue(success)

    @patch('subprocess.run')
    @patch('sys.stdout', new_callable=MagicMock)
    def test_run_missing_module(self, mock_stdout, mock_run):
        # Mock failure
        mock_err = subprocess.CalledProcessError(1, ["python", "app.py"])
        mock_err.stderr = "ModuleNotFoundError: No module named 'rich'"
        mock_run.side_effect = mock_err
        
        success = healer.run_with_healing(["python", "app.py"])
        self.assertFalse(success)
        
        output = "".join(call[0][0] for call in mock_stdout.write.call_args_list)
        self.assertIn("Detected missing module: rich", output)
        self.assertIn("Suggesting installation: pip install rich", output)

    @patch('subprocess.run')
    @patch('os.chmod')
    def test_run_permission_denied(self, mock_chmod, mock_run):
        script = self.test_root / "script.py"
        script.write_text("print(1)")
        
        mock_err = subprocess.CalledProcessError(1, [str(script)])
        mock_err.stderr = "Permission denied"
        mock_run.side_effect = mock_err
        
        healer.run_with_healing([str(script)])
        self.assertTrue(mock_chmod.called)

    @patch('subprocess.run')
    def test_generate_repair_request(self, mock_run):
        script = Path("failing.py")
        script.write_text("import non_existent")
        
        mock_err = subprocess.CalledProcessError(1, ["python3", "failing.py"])
        mock_err.stderr = "ModuleNotFoundError: No module named 'missing'"
        mock_run.side_effect = mock_err
        
        healer.run_with_healing(["python3", "failing.py"])
        
        bus_dir = Path(".agent/bus/outputs")
        files = list(bus_dir.glob("repair_*.json"))
        self.assertEqual(len(files), 1)
        
        data = json.loads(files[0].read_text())
        self.assertEqual(data["script_path"], "failing.py")
        self.assertEqual(data["status"], "waiting_for_fix")

if __name__ == "__main__":
    unittest.main()
