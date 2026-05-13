#!/usr/bin/env python3
import unittest
import shutil
import sys
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

import delivery.task_tracer as tracer

class TestTaskTracer(unittest.TestCase):
    def setUp(self):
        self.test_root = REPO_ROOT / "scratch" / "test_tracer"
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.patch_repo = patch('delivery.task_tracer.REPO_ROOT', self.test_root)
        self.patch_repo.start()

    def tearDown(self):
        self.patch_repo.stop()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    @patch('subprocess.check_output')
    def test_get_staged_files(self, mock_git):
        mock_git.return_value = b"file1.py\nfile2.md\n"
        files = tracer.get_staged_files()
        self.assertEqual(files, ["file1.py", "file2.md"])

    def test_find_active_task(self):
        tasks_dir = self.test_root / "tasks"
        tasks_dir.mkdir()
        
        t1 = tasks_dir / "task1.md"
        t1.write_text("old")
        
        # Ensure different mtimes
        import time
        time.sleep(0.01)
        
        t2 = tasks_dir / "task2.md"
        t2.write_text("new")
        
        active = tracer.find_active_task()
        self.assertEqual(active.name, "task2.md")

    def test_update_task_card_new_marker(self):
        task_path = self.test_root / "task.md"
        task_path.write_text("# Task Title")
        
        tracer.update_task_card(task_path, ["script.py"])
        
        content = task_path.read_text()
        self.assertIn("## 📂 Changed Files", content)
        self.assertIn("- `script.py`", content)
        self.assertIn("Auto-trace", content)

    def test_update_task_card_existing_marker(self):
        task_path = self.test_root / "task.md"
        task_path.write_text("# Task Title\n\n## 📂 Changed Files\n- `old.py`")
        
        tracer.update_task_card(task_path, ["new.py"])
        
        content = task_path.read_text()
        self.assertIn("- `old.py`", content)
        self.assertIn("- `new.py`", content)

if __name__ == "__main__":
    unittest.main()
