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

import context.bus_manager as bus

class TestBusManager(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_bus_manager").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.bus_dir = self.test_root / ".agent" / "bus"
        self.bus_dir.mkdir(parents=True)
        self.bus_file = self.bus_dir / "context.json"
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)
        
        # Patch paths
        self.patch_bus_dir = patch('context.bus_manager.BUS_DIR', self.bus_dir)
        self.patch_bus_file = patch('context.bus_manager.BUS_FILE', self.bus_file)
        self.patch_bus_dir.start()
        self.patch_bus_file.start()

    def tearDown(self):
        self.patch_bus_dir.stop()
        self.patch_bus_file.stop()
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_push_pull(self):
        bus.push("obj1", "requirement", "test-agent", '{"key": "val"}')
        
        # Capture output of pull
        with patch('sys.stdout', new=MagicMock()) as mock_stdout:
            bus.pull("obj1")
            output = mock_stdout.write.call_args_list[0][0][0]
            data = json.loads(output)
            self.assertEqual(data["id"], "obj1")
            self.assertEqual(data["content"]["key"], "val")

    def test_push_invalid_type(self):
        with self.assertRaises(SystemExit):
            bus.push("obj1", "invalid-type", "test", "content")

    def test_push_duplicate(self):
        bus.push("obj1", "requirement", "test", "content")
        with self.assertRaises(SystemExit):
            bus.push("obj1", "requirement", "test", "content")

    def test_delete(self):
        bus.push("obj1", "requirement", "test", "content")
        bus.delete("obj1")
        data = json.loads(self.bus_file.read_text())
        self.assertEqual(len(data["objects"]), 0)

    def test_clear(self):
        bus.push("obj1", "requirement", "test", "content")
        bus.clear()
        data = json.loads(self.bus_file.read_text())
        self.assertEqual(len(data["objects"]), 0)

    def test_list_objects(self):
        bus.push("obj1", "requirement", "test", "content")
        with patch('sys.stdout', new=MagicMock()) as mock_stdout:
            bus.list_objects()
            self.assertTrue(any("obj1" in str(call) for call in mock_stdout.write.call_args_list))

    def test_wait_for_object(self):
        # Simulate background push
        def slow_push():
            time.sleep(1)
            bus.push("obj1", "requirement", "test", "content")
        
        import threading
        import time
        thread = threading.Thread(target=slow_push)
        thread.start()
        
        obj = bus.wait_for_object("obj1", timeout=5)
        self.assertIsNotNone(obj)
        self.assertEqual(obj["id"], "obj1")
        thread.join()

    def test_get_objects_by_type(self):
        bus.push("obj1", "requirement", "test", "content")
        bus.push("obj2", "incident", "test", "content")
        
        objs = bus.get_objects_by_type("requirement")
        self.assertEqual(len(objs), 1)
        self.assertEqual(objs[0]["id"], "obj1")

    def test_clean_author(self):
        bus.push("obj1", "requirement", "author1", "content")
        bus.push("obj2", "requirement", "author2", "content")
        
        bus.clean_author("author1")
        data = json.loads(self.bus_file.read_text())
        self.assertEqual(len(data["objects"]), 1)
        self.assertEqual(data["objects"][0]["author"], "author2")

    @patch('sys.stderr', new_callable=MagicMock)
    def test_check_telemetry_limits(self, mock_stderr):
        rules_file = self.test_root / "rules.json"
        rules_file.write_text(json.dumps({
            "limits": {
                "token_budget_per_task": 100,
                "cost_limit_per_task_usd": 0.01
            }
        }))
        
        with patch('context.bus_manager.WATCHDOG_RULES_PATH', rules_file):
            # Normal push should not alert (check for 'BUS ALERT' specifically)
            bus.push("tel1", "telemetry", "test", '{"total_tokens": 50, "total_cost_usd": 0.005}')
            calls = "".join(str(call) for call in mock_stderr.write.call_args_list)
            self.assertNotIn("BUS ALERT", calls)
            
            # Breach push should alert
            bus.push("tel2", "telemetry", "test", '{"total_tokens": 150, "total_cost_usd": 0.02}')
            calls = "".join(str(call) for call in mock_stderr.write.call_args_list)
            self.assertIn("BUS ALERT", calls)

if __name__ == "__main__":
    unittest.main()
