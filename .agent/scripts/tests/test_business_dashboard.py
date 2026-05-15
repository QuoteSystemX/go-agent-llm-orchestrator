#!/usr/bin/env python3
import unittest
import shutil
import sys
import os
import io
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

import health.business_dashboard as dashboard

class TestBusinessDashboard(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_dashboard").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        self.tasks_dir = self.test_root / "tasks"
        self.tasks_dir.mkdir()
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)
        
        # Patch paths
        self.patch_root = patch('health.business_dashboard.REPO_ROOT', self.test_root)
        self.patch_tasks = patch('health.business_dashboard.TASKS_DIR', self.tasks_dir)
        self.patch_root.start()
        self.patch_tasks.start()

    def tearDown(self):
        self.patch_root.stop()
        self.patch_tasks.stop()
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_parse_tasks_with_epics(self):
        # Create tasks
        (self.tasks_dir / "task1.md").write_text("Epic: Auth\nStatus: [x]")
        (self.tasks_dir / "task2.md").write_text("Epic: Auth\nStatus: [ ]")
        (self.tasks_dir / "task3.md").write_text("Epic: UI\nStatus: [x]")
        
        features, sprints = dashboard.parse_tasks()
        
        self.assertEqual(features["Auth"]["total"], 2)
        self.assertEqual(features["Auth"]["completed"], 1)
        self.assertEqual(features["UI"]["total"], 1)
        self.assertEqual(features["UI"]["completed"], 1)

    def test_parse_tasks_empty(self):
        shutil.rmtree(self.tasks_dir)
        features, sprints = dashboard.parse_tasks()
        self.assertIsNone(features)

    @patch('sys.stdout', new_callable=io.StringIO)
    def test_show_dashboard_no_rich(self, mock_stdout):
        # Force non-rich mode for simpler output testing
        with patch('health.business_dashboard.HAS_RICH', False):
            (self.tasks_dir / "task.md").write_text("Epic: Core\n[x] Done")
            dashboard.show_dashboard()
            
            output = mock_stdout.getvalue()
            self.assertIn("Business Progress Dashboard", output)
            self.assertIn("Core: 100.0%", output)

if __name__ == "__main__":
    unittest.main()
