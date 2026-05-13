#!/usr/bin/env python3
import unittest
import shutil
import sys
import os
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev", "misc"]:
        sys.path.append(str(REPO_ROOT / ".agent" / "scripts" / domain))

import health.wsl_health_collector as wsl_health

class TestWSLHealthCollector(unittest.TestCase):
    def setUp(self):
        self.collector = wsl_health.WSLHealthCollector()
        self.collector.save = MagicMock()
        self.collector.add_metric = MagicMock()

    @patch('os.path.exists')
    def test_collect_not_wsl(self, mock_exists):
        # Setup so /proc/version doesn't exist
        mock_exists.return_value = False
        
        self.collector.collect()
        
        self.collector.save.assert_not_called()
        self.assertEqual(self.collector.add_metric.call_count, 0)

    @patch('health.wsl_health_collector.discover_ollama_url')
    @patch('subprocess.run')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data="microsoft standard wsl")
    def test_collect_wsl_healthy(self, mock_open, mock_exists, mock_run, mock_discover):
        # /proc/version exists and /mnt/c exists
        def side_effect(path):
            if path == "/proc/version": return True
            if path == "/mnt/c": return True
            return False
        mock_exists.side_effect = side_effect
        
        mock_discover.return_value = "http://172.31.0.1:11434"
        
        # Ping successful
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_run.return_value = mock_process
        
        with patch('sys.stdout', new=MagicMock()):
            self.collector.collect()
            
        self.collector.save.assert_called_once()
        self.assertEqual(self.collector.status, "PASS")
        self.collector.add_metric.assert_any_call("gateway_ip", "172.31.0.1", "PASS")
        self.collector.add_metric.assert_any_call("host_connectivity", "UP", "PASS")
        self.collector.add_metric.assert_any_call("mount_c", "AVAILABLE", "PASS")

    @patch('health.wsl_health_collector.discover_ollama_url')
    @patch('subprocess.run')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data="microsoft standard wsl")
    def test_collect_wsl_unhealthy(self, mock_open, mock_exists, mock_run, mock_discover):
        def side_effect(path):
            if path == "/proc/version": return True
            if path == "/mnt/c": return False
            return False
        mock_exists.side_effect = side_effect
        
        mock_discover.return_value = "http://172.31.0.1:11434"
        
        # Ping fails
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_run.return_value = mock_process
        
        with patch('sys.stdout', new=MagicMock()):
            self.collector.collect()
            
        self.collector.save.assert_called_once()
        self.assertEqual(self.collector.status, "WARN")
        self.collector.add_metric.assert_any_call("host_connectivity", "DOWN", "WARN")
        self.collector.add_metric.assert_any_call("mount_c", "MISSING", "WARN")

if __name__ == "__main__":
    unittest.main()
