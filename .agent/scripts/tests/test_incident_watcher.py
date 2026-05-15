#!/usr/bin/env python3
import unittest
import shutil
import sys
import os
import json
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

import health.incident_watcher as watcher

class TestIncidentWatcher(unittest.TestCase):
    @patch('subprocess.Popen')
    @patch('health.incident_watcher.bus_manager.push')
    @patch('subprocess.getoutput', return_value="M test.py")
    def test_watch_command_success(self, mock_git, mock_push, mock_popen):
        # Mock successful process
        mock_process = MagicMock()
        mock_process.communicate.return_value = ("output", "")
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        
        result = watcher.watch_command(["ls", "-l"])
        self.assertTrue(result)
        mock_push.assert_not_called()

    @patch('subprocess.Popen')
    @patch('health.incident_watcher.bus_manager.push')
    @patch('subprocess.getoutput', return_value="M test.py")
    def test_watch_command_failure(self, mock_git, mock_push, mock_popen):
        # Mock failed process
        mock_process = MagicMock()
        mock_process.communicate.return_value = ("", "error message")
        mock_process.returncode = 1
        mock_popen.return_value = mock_process
        
        with patch('sys.stdout', new=MagicMock()), patch('sys.stderr', new=MagicMock()):
            result = watcher.watch_command(["python3", "test_runner.py"])
            
        self.assertFalse(result)
        mock_push.assert_called_once()
        
        # Verify severity logic
        args, kwargs = mock_push.call_args
        payload = json.loads(args[3])
        self.assertEqual(payload["severity"], "high") # contains 'test'
        self.assertEqual(payload["stderr"], "error message")

if __name__ == "__main__":
    unittest.main()
