#!/usr/bin/env python3
import unittest
import shutil
import sys
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

import delivery.task_miner as miner

class TestTaskMiner(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_task_miner").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        (self.test_root / "tasks").mkdir()
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)
        
        # Patch REPO_ROOT
        self.patch_root = patch('delivery.task_miner.REPO_ROOT', self.test_root)
        self.patch_root.start()

    def tearDown(self):
        self.patch_root.stop()
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_slugify(self):
        self.assertEqual(miner.slugify("Hello World!"), "hello-world")
        self.assertEqual(miner.slugify("Test @#$%^&* Item"), "test-item")

    def test_mine_roadmap(self):
        roadmap = """
## Current
- [x] Task 1

## Planned
- [ ] Task 2
- Task 3
"""
        (self.test_root / "ROADMAP.md").write_text(roadmap)
        
        tasks = miner.mine_roadmap()
        titles = [t["title"] for t in tasks]
        self.assertIn("Task 2", titles)
        self.assertIn("Task 3", titles)
        self.assertNotIn("Task 1", titles)

    def test_create_task_card(self):
        task = {"title": "New Task", "section": "Planned"}
        success = miner.create_task_card(task)
        
        self.assertTrue(success)
        task_files = list((self.test_root / "tasks").glob("*.md"))
        self.assertEqual(len(task_files), 1)
        content = task_files[0].read_text()
        self.assertIn("# [STORY] New Task", content)
        self.assertIn("Planned", content)

    @patch('sys.stdout', new_callable=MagicMock)
    def test_main_dry_run(self, mock_stdout):
        (self.test_root / "ROADMAP.md").write_text("## Planned\n- [ ] Dry Task")
        
        with patch('sys.argv', ['task_miner.py', '--dry-run']):
            miner.main()
            
        output = "".join(call[0][0] for call in mock_stdout.write.call_args_list)
        self.assertIn("Found: Dry Task", output)
        self.assertEqual(len(list((self.test_root / "tasks").glob("*.md"))), 0)

if __name__ == "__main__":
    unittest.main()
