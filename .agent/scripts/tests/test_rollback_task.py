#!/usr/bin/env python3
import unittest
import shutil
import sys
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

import delivery.rollback_task as rollback

class TestRollbackTask(unittest.TestCase):
    def setUp(self):
        self.test_root = REPO_ROOT / "scratch" / "test_rollback"
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.bus_dir = self.test_root / ".agent" / "bus"
        self.bus_dir.mkdir(parents=True)
        
        self.patch_repo = patch('delivery.rollback_task.REPO_ROOT', self.test_root)
        self.patch_bus = patch('delivery.rollback_task.BUS_DIR', self.bus_dir)
        
        self.patch_repo.start()
        self.patch_bus.start()

    def tearDown(self):
        self.patch_repo.stop()
        self.patch_bus.stop()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    @patch('subprocess.check_call')
    def test_rollback_git(self, mock_call):
        success = rollback.rollback_git()
        self.assertTrue(success)
        self.assertEqual(mock_call.call_count, 2)
        mock_call.assert_any_call(["git", "reset", "--hard", "HEAD"], cwd=self.test_root)

    def test_clean_bus_by_author(self):
        bus_file = self.bus_dir / "context.json"
        initial_data = {
            "objects": [
                {"id": "o1", "author": "agent-a"},
                {"id": "o2", "author": "agent-b"},
                {"id": "o3", "author": "agent-a"}
            ]
        }
        bus_file.write_text(json.dumps(initial_data))
        
        rollback.clean_bus(author_filter="agent-a")
        
        final_data = json.loads(bus_file.read_text())
        self.assertEqual(len(final_data["objects"]), 1)
        self.assertEqual(final_data["objects"][0]["author"], "agent-b")

    def test_clean_bus_default(self):
        bus_file = self.bus_dir / "context.json"
        # 7 objects
        initial_data = {"objects": [{"id": f"o{i}"} for i in range(7)]}
        bus_file.write_text(json.dumps(initial_data))
        
        rollback.clean_bus()
        
        final_data = json.loads(bus_file.read_text())
        self.assertEqual(len(final_data["objects"]), 2) # 7 - 5 = 2

if __name__ == "__main__":
    unittest.main()
