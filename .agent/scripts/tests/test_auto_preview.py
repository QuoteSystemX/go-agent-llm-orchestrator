#!/usr/bin/env python3
import unittest
import shutil
import sys
import json
import os
import signal
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

import delivery.auto_preview as preview

class TestAutoPreview(unittest.TestCase):
    def setUp(self):
        self.test_root = REPO_ROOT / "scratch" / "test_preview"
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.agent_dir = self.test_root / ".agent"
        self.agent_dir.mkdir(parents=True)
        
        self.patch_agent = patch('delivery.auto_preview.AGENT_DIR', self.agent_dir)
        self.patch_pid = patch('delivery.auto_preview.PID_FILE', self.agent_dir / "preview.pid")
        self.patch_log = patch('delivery.auto_preview.LOG_FILE', self.agent_dir / "preview.log")
        self.patch_root = patch('delivery.auto_preview.get_project_root', return_value=self.test_root)
        
        self.patch_agent.start()
        self.patch_pid.start()
        self.patch_log.start()
        self.patch_root.start()

    def tearDown(self):
        self.patch_agent.stop()
        self.patch_pid.stop()
        self.patch_log.stop()
        self.patch_root.stop()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_get_start_command(self):
        pkg_file = self.test_root / "package.json"
        pkg_file.write_text(json.dumps({"scripts": {"dev": "vite"}}))
        
        cmd = preview.get_start_command(self.test_root)
        self.assertEqual(cmd, ["npm", "run", "dev"])
        
        pkg_file.write_text(json.dumps({"scripts": {"start": "node index.js"}}))
        cmd = preview.get_start_command(self.test_root)
        self.assertEqual(cmd, ["npm", "start"])

    @patch('os.kill')
    def test_is_running(self, mock_kill):
        mock_kill.return_value = None
        self.assertTrue(preview.is_running(1234))
        
        mock_kill.side_effect = OSError()
        self.assertFalse(preview.is_running(1234))

    @patch('subprocess.Popen')
    @patch('delivery.auto_preview.is_running', return_value=False)
    def test_start_server(self, mock_run, mock_popen):
        pkg_file = self.test_root / "package.json"
        pkg_file.write_text(json.dumps({"scripts": {"dev": "vite"}}))
        
        mock_proc = MagicMock()
        mock_proc.pid = 9999
        mock_popen.return_value = mock_proc
        
        preview.start_server(port=4000)
        
        pid_file = self.agent_dir / "preview.pid"
        self.assertTrue(pid_file.exists())
        self.assertEqual(pid_file.read_text(), "9999")
        self.assertTrue(mock_popen.called)

    @patch('os.kill')
    @patch('delivery.auto_preview.is_running', return_value=True)
    def test_stop_server(self, mock_run, mock_kill):
        pid_file = self.agent_dir / "preview.pid"
        pid_file.write_text("9999")
        
        preview.stop_server()
        
        self.assertFalse(pid_file.exists())
        if sys.platform != 'win32':
            mock_kill.assert_called_with(9999, signal.SIGTERM)

if __name__ == "__main__":
    unittest.main()
