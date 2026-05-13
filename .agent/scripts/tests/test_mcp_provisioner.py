#!/usr/bin/env python3
import unittest
import shutil
import sys
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

import health.mcp_provisioner as provisioner

class TestMCPProvisioner(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_mcp_provisioner").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.server_dir = self.test_root / ".agent" / "local-skill-server"
        self.server_dir.mkdir(parents=True)
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)
        
        self.patch_root = patch('health.mcp_provisioner.get_repo_root', return_value=self.test_root)
        self.patch_root.start()

    def tearDown(self):
        self.patch_root.stop()
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    @patch('subprocess.Popen')
    def test_check_mcp_health_success(self, mock_popen):
        # Mock Popen to simulate a successful fast exit
        mock_process = MagicMock()
        mock_process.communicate.return_value = ("stdout", "stderr")
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        
        # Create launcher so it exists
        (self.server_dir / "local-skill-server.sh").write_text("")
        
        is_healthy, msg = provisioner.check_mcp_health()
        self.assertTrue(is_healthy)
        self.assertIn("started and exited successfully", msg)

    @patch('subprocess.Popen')
    def test_check_mcp_health_timeout(self, mock_popen):
        # Mock Popen to simulate a running daemon
        mock_process = MagicMock()
        mock_process.communicate.side_effect = subprocess.TimeoutExpired(cmd="cmd", timeout=2)
        mock_popen.return_value = mock_process
        
        (self.server_dir / "local-skill-server.sh").write_text("")
        
        is_healthy, msg = provisioner.check_mcp_health()
        self.assertTrue(is_healthy)
        self.assertIn("running/responsive", msg)
        mock_process.kill.assert_called_once()

    @patch('subprocess.Popen')
    def test_check_mcp_health_failure(self, mock_popen):
        # Mock Popen to simulate failure
        mock_process = MagicMock()
        mock_process.communicate.return_value = ("", "error")
        mock_process.returncode = 1
        mock_popen.return_value = mock_process
        
        (self.server_dir / "local-skill-server.sh").write_text("")
        
        is_healthy, msg = provisioner.check_mcp_health()
        self.assertFalse(is_healthy)
        self.assertIn("failed", msg)

    @patch('subprocess.run')
    @patch('pathlib.Path.home')
    def test_provision_mcp(self, mock_home, mock_run):
        # Setup home dir mock
        home_dir = self.test_root / "home"
        home_dir.mkdir()
        mock_home.return_value = home_dir
        
        result = provisioner.provision_mcp()
        self.assertTrue(result)
        
        # Verify launcher script created
        launcher = self.server_dir / "local-skill-server.sh"
        self.assertTrue(launcher.exists())
        self.assertIn("#!/bin/bash", launcher.read_text())
        
        # Verify shim created
        shim = home_dir / ".local" / "bin" / "agent-kit-server"
        self.assertTrue(shim.exists())
        self.assertTrue(shim.is_symlink())

    @patch('sys.exit')
    @patch('health.mcp_provisioner.check_mcp_health')
    def test_main_healthy(self, mock_check, mock_exit):
        mock_check.return_value = (True, "OK")
        with patch('sys.stdout', new=MagicMock()):
            provisioner.main()
        mock_exit.assert_called_with(0)

if __name__ == "__main__":
    unittest.main()
