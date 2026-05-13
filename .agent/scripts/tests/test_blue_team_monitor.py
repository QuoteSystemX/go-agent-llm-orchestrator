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

import health.blue_team_monitor as monitor

class TestBlueTeamMonitor(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_blue_team").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.bus_dir = self.test_root / ".agent" / "bus"
        self.bus_dir.mkdir(parents=True)
        self.metrics_file = self.bus_dir / "metrics_log.json"
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)
        
        # Patch paths
        self.patch_root = patch('health.blue_team_monitor.REPO_ROOT', self.test_root)
        self.patch_bus = patch('health.blue_team_monitor.BUS_DIR', self.bus_dir)
        self.patch_metrics = patch('health.blue_team_monitor.METRICS_FILE', self.metrics_file)
        self.patch_root.start()
        self.patch_bus.start()
        self.patch_metrics.start()

    def tearDown(self):
        self.patch_root.stop()
        self.patch_bus.stop()
        self.patch_metrics.stop()
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    def test_get_system_metrics(self, mock_disk, mock_ram, mock_cpu):
        mock_cpu.return_value = 10.0
        mock_ram.return_value.percent = 40.0
        mock_disk.return_value.free = 100 * (1024**3) # 100GB
        
        metrics = monitor.get_system_metrics()
        self.assertEqual(metrics["cpu_percent"], 10.0)
        self.assertEqual(metrics["ram_percent"], 40.0)
        self.assertAlmostEqual(metrics["disk_free_gb"], 100.0)

    @patch('subprocess.run')
    def test_check_mcp_server(self, mock_run):
        # Healthy
        mock_run.return_value = MagicMock(returncode=0, stdout="All systems go")
        healthy, msg = monitor.check_mcp_server()
        self.assertTrue(healthy)
        self.assertEqual(msg, "All systems go")
        
        # Down
        mock_run.return_value = MagicMock(returncode=1, stdout="Server crashed")
        healthy, msg = monitor.check_mcp_server()
        self.assertFalse(healthy)
        self.assertEqual(msg, "Server crashed")

    def test_log_metrics_rolling(self):
        metrics = {"cpu": 1}
        # Create 110 entries
        for i in range(110):
            monitor.log_metrics(metrics, "HEALTHY")
            
        with open(self.metrics_file, "r") as f:
            history = json.load(f)
            self.assertEqual(len(history), 100) # Capped at 100

if __name__ == "__main__":
    unittest.main()
