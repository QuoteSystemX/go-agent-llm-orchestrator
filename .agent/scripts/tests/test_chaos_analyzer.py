#!/usr/bin/env python3
import unittest
import shutil
import sys
import json
import os
import time
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

import chaos.chaos_analyzer as analyzer

class TestChaosAnalyzer(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_chaos_analyzer").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.bus_dir = self.test_root / ".agent" / "bus"
        self.bus_dir.mkdir(parents=True)
        self.chaos_file = self.bus_dir / "chaos_event.json"
        self.blue_file = self.bus_dir / "blue_team_status.json"
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)
        
        # Patch paths
        self.patch_root = patch('chaos.chaos_analyzer.REPO_ROOT', self.test_root)
        self.patch_bus = patch('chaos.chaos_analyzer.BUS_DIR', self.bus_dir)
        self.patch_chaos = patch('chaos.chaos_analyzer.CHAOS_EVENT_FILE', self.chaos_file)
        self.patch_blue = patch('chaos.chaos_analyzer.BLUE_STATUS_FILE', self.blue_file)
        self.patch_root.start()
        self.patch_bus.start()
        self.patch_chaos.start()
        self.patch_blue.start()

    def tearDown(self):
        self.patch_root.stop()
        self.patch_bus.stop()
        self.patch_chaos.stop()
        self.patch_blue.stop()
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    @patch('sys.stdout', new_callable=MagicMock)
    def test_no_chaos_event(self, mock_stdout):
        with self.assertRaises(SystemExit):
            analyzer.main()
        output = "".join(call[0][0] for call in mock_stdout.write.call_args_list)
        self.assertIn("No active chaos events", output)

    @patch('time.sleep', side_effect=[None])
    @patch('time.time')
    @patch('sys.stdout', new_callable=MagicMock)
    def test_recovery_success(self, mock_stdout, mock_time, mock_sleep):
        start_time = 1000
        mock_time.return_value = 1005 # Recovery time
        
        with open(self.chaos_file, "w") as f:
            json.dump({"timestamp": start_time, "args": ["cpu_spike"]}, f)
            
        with open(self.blue_file, "w") as f:
            json.dump({"status": "HEALTHY"}, f)
            
        analyzer.main()
        
        output = "".join(call[0][0] for call in mock_stdout.write.call_args_list)
        self.assertIn("SYSTEM RECOVERED", output)
        self.assertIn("MTTR", output)
        
        with open(self.bus_dir / "chaos_report.json", "r") as f:
            report = json.load(f)
            self.assertEqual(report["status"], "SUCCESS")
            self.assertEqual(report["mttr"], 5)

    @patch('time.sleep', side_effect=[None]*60)
    @patch('sys.stdout', new_callable=MagicMock)
    def test_recovery_failure(self, mock_stdout, mock_sleep):
        with open(self.chaos_file, "w") as f:
            json.dump({"timestamp": time.time(), "args": ["kill_process"]}, f)
            
        # Blue team file stays DOWN or missing
        with open(self.blue_file, "w") as f:
            json.dump({"status": "DOWN"}, f)
            
        analyzer.main()
        
        output = "".join(call[0][0] for call in mock_stdout.write.call_args_list)
        self.assertIn("FAILED TO RECOVER", output)

if __name__ == "__main__":
    unittest.main()
