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

import chaos.chaos_monkey as monkey

class TestChaosMonkey(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_chaos_monkey").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.bus_dir = self.test_root / ".agent" / "bus"
        self.bus_dir.mkdir(parents=True)
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)
        
        # Patch paths
        self.patch_bus = patch('chaos.chaos_monkey.BUS_DIR', self.bus_dir)
        self.patch_bus.start()

    def tearDown(self):
        self.patch_bus.stop()
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    @patch('subprocess.run')
    def test_kill_mcp(self, mock_run):
        monkey.kill_mcp()
        self.assertTrue(mock_run.called)
        # Check if pkill was called
        args, kwargs = mock_run.call_args_list[0]
        self.assertIn("pkill", args[0])

    def test_corrupt_bus(self):
        target = self.bus_dir / "test.json"
        target.write_text('{"key": "value"}')
        
        monkey.corrupt_bus()
        content = target.read_text()
        self.assertNotEqual(content, '{"key": "value"}')

    @patch('time.sleep')
    def test_inject_latency(self, mock_sleep):
        monkey.inject_latency()
        mock_sleep.assert_called_with(5)

    def test_cpu_spike(self):
        start = time.time()
        monkey.cpu_spike(duration=0.1)
        end = time.time()
        self.assertGreaterEqual(end - start, 0.1)

    @patch('time.sleep')
    def test_memory_leak(self, mock_sleep):
        monkey.memory_leak(mb=1) # Small leak for test
        mock_sleep.assert_called_with(5)

    @patch('chaos.chaos_monkey.CHAOS_ENABLED', True)
    @patch('sys.argv', ['chaos_monkey.py', '--latency'])
    def test_main_logging(self):
        with patch('chaos.chaos_monkey.inject_latency', return_value=True):
            monkey.main()
            
        chaos_log = self.bus_dir / "chaos_event.json"
        self.assertTrue(chaos_log.exists())
        data = json.loads(chaos_log.read_text())
        self.assertEqual(data["type"], "chaos_injection")
        self.assertIn("--latency", data["args"])

if __name__ == "__main__":
    unittest.main()
