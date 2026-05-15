#!/usr/bin/env python3
import unittest
import shutil
import sys
import os
import json
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

import health.budget_monitor as budget

class TestBudgetMonitor(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_budget_monitor").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.bus_dir = self.test_root / ".agent" / "bus"
        self.bus_dir.mkdir(parents=True)
        
        self.rules_dir = self.test_root / ".agent" / "rules"
        self.rules_dir.mkdir(parents=True)
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)
        
        # Patch paths
        self.patch_root = patch('health.budget_monitor.REPO_ROOT', self.test_root)
        self.patch_bus = patch('health.budget_monitor.BUS_DIR', self.bus_dir)
        self.patch_guardrails = patch('health.budget_monitor.GUARDRAILS_FILE', self.rules_dir / "guardrails.json")
        
        self.patch_root.start()
        self.patch_bus.start()
        self.patch_guardrails.start()

    def tearDown(self):
        self.patch_root.stop()
        self.patch_bus.stop()
        self.patch_guardrails.stop()
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_load_guardrails_default(self):
        limits = budget.load_guardrails()
        self.assertEqual(limits["session_token_limit"], 50000)

    def test_load_guardrails_custom(self):
        custom = {"session_token_limit": 1000}
        (self.rules_dir / "guardrails.json").write_text(json.dumps(custom))
        limits = budget.load_guardrails()
        self.assertEqual(limits["session_token_limit"], 1000)

    @patch('health.budget_monitor.get_current_usage', return_value=30000) # 60%
    @patch('os.environ.get', return_value="LOW")
    @patch('sys.exit')
    def test_throttling(self, mock_exit, mock_env, mock_usage):
        with patch('sys.stdout', new=MagicMock()):
            budget.main()
        mock_exit.assert_called_with(1)
        
        # Check bus status
        status_file = self.bus_dir / "budget_status.json"
        data = json.loads(status_file.read_text())
        self.assertEqual(data["status"], "THROTTLED")

    @patch('health.budget_monitor.get_current_usage', return_value=55000) # >100%
    @patch('sys.exit')
    def test_blocking(self, mock_exit, mock_usage):
        with patch('sys.stdout', new=MagicMock()):
            budget.main()
        mock_exit.assert_called_with(1)
        
        status_file = self.bus_dir / "budget_status.json"
        data = json.loads(status_file.read_text())
        self.assertEqual(data["status"], "BLOCKED")

if __name__ == "__main__":
    unittest.main()
