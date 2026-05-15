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

import delivery.task_sync as sync

class TestTaskSync(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_task_sync").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.bus_dir = self.test_root / ".agent" / "bus" / "outputs"
        self.bus_dir.mkdir(parents=True)
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)
        
        # Patch paths
        self.patch_bus = patch('delivery.task_sync.BUS_DIR', str(self.bus_dir))
        self.patch_bus.start()

    def tearDown(self):
        self.patch_bus.stop()
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_find_app_data_path(self):
        # Create a mock brain file
        brain_dir = self.test_root / "brain" / "b6e6196a-8f3d-49cf-b328-148123206a3c"
        brain_dir.mkdir(parents=True)
        target = brain_dir / "test.md"
        target.write_text("test")
        
        with patch.dict(os.environ, {"AGENT_APP_DATA_DIR": str(self.test_root)}):
            path = sync.find_app_data_path("test.md")
            self.assertEqual(path, str(target))

    def test_get_latest_goal(self):
        (self.bus_dir / "1.json").write_text(json.dumps({"goal": "First Goal"}))
        (self.bus_dir / "2.json").write_text(json.dumps({"goal": "Latest Goal"}))
        
        goal = sync.get_latest_goal()
        self.assertEqual(goal, "latest goal")

    def test_sync_tasks(self):
        # Latest goal
        (self.bus_dir / "1.json").write_text(json.dumps({"goal": "implementing database encryption"}))
        
        # Task file
        task_file = self.test_root / "tasks.md"
        task_file.write_text("- [ ] Setup Database Encryption\n- [ ] Unrelated Task")
        
        with patch('delivery.task_sync.TASK_PATH', str(task_file)):
            sync.sync_tasks()
            
        content = task_file.read_text()
        self.assertIn("- [x] Setup Database Encryption", content)
        self.assertIn("- [ ] Unrelated Task", content)

if __name__ == "__main__":
    unittest.main()
