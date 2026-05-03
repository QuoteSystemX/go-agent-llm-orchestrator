import unittest
import os
import shutil
from pathlib import Path
from datetime import datetime

# Add scripts to path
import sys
SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(SCRIPTS_DIR))

from lib.paths import REPO_ROOT
import task_tracer

class TestTaskTracer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_tasks_dir = REPO_ROOT / "tasks"
        cls.test_tasks_dir.mkdir(exist_ok=True)
        cls.test_task_file = cls.test_tasks_dir / "test-tracer-card.md"
        cls.test_task_file.write_text("# Test Task\nStatus: Pending\n", encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        if cls.test_task_file.exists():
            cls.test_task_file.unlink()

    def test_find_active_task(self):
        task = task_tracer.find_active_task()
        self.assertIsNotNone(task)
        self.assertEqual(task.name, "test-tracer-card.md")

    def test_update_task_card(self):
        files = ["file1.py", "file2.go"]
        msg = task_tracer.update_task_card(self.test_task_file, files)
        self.assertIn("Updated task card", msg)
        
        content = self.test_task_file.read_text(encoding="utf-8")
        self.assertIn("## 📂 Измененные файлы", content)
        self.assertIn("- file1.py", content.replace("`", "")) # Simple check

if __name__ == "__main__":
    unittest.main()
