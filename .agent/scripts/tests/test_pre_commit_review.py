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

import dev.pre_commit_review as reviewer

class TestPreCommitReview(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_pre_commit_review").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.lessons_path = self.test_root / "LESSONS_LEARNED.md"
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)
        
        self.patch_root = patch('dev.pre_commit_review.REPO_ROOT', self.test_root)
        self.patch_lessons = patch('dev.pre_commit_review.LESSONS_PATH', self.lessons_path)
        self.patch_root.start()
        self.patch_lessons.start()

    def tearDown(self):
        self.patch_root.stop()
        self.patch_lessons.stop()
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    @patch('subprocess.check_output', return_value=b"diff")
    def test_get_staged_diff(self, mock_subprocess):
        diff = reviewer.get_staged_diff()
        self.assertEqual(diff, "diff")

    @patch('dev.pre_commit_review.get_staged_diff', return_value="")
    def test_review_diff_empty(self, mock_diff):
        ok, msg = reviewer.review_diff()
        self.assertTrue(ok)
        self.assertIn("No staged changes", msg)

    @patch('dev.pre_commit_review.get_staged_diff', return_value="+ Added code-archaeologist")
    def test_review_diff_with_warnings(self, mock_diff):
        self.lessons_path.write_text("### [2026-05-13] [agent] [code-archaeologist] Use specific tools")
        
        # Mock health and conflict resolver to pass
        with patch.dict('sys.modules', {'status_report': MagicMock(get_health_report=lambda: {"score": 100}), 
                                        'conflict_resolver': MagicMock(resolve_conflicts=lambda: None),
                                        'task_tracer': MagicMock()}):
            ok, msg = reviewer.review_diff()
            
        self.assertFalse(ok)
        self.assertIn("Review finished with warnings", msg)

    @patch('dev.pre_commit_review.get_staged_diff', return_value="+ Clean code")
    def test_review_diff_low_health(self, mock_diff):
        self.lessons_path.write_text("### [2026-05-13] [test] Test")
        
        with patch.dict('sys.modules', {'status_report': MagicMock(get_health_report=lambda: {"score": 50})}):
            with patch('sys.stdout', new=MagicMock()):
                ok, msg = reviewer.review_diff()
                
        self.assertFalse(ok)
        self.assertIn("Low health score", msg)

    @patch('dev.pre_commit_review.get_staged_diff', return_value="+ Clean code")
    def test_review_diff_conflict(self, mock_diff):
        self.lessons_path.write_text("### [2026-05-13] [test] Test")
        
        with patch.dict('sys.modules', {'status_report': MagicMock(get_health_report=lambda: {"score": 100}),
                                        'conflict_resolver': MagicMock(resolve_conflicts=lambda: "⚠️ Conflict")}):
            with patch('sys.stdout', new=MagicMock()):
                ok, msg = reviewer.review_diff()
                
        self.assertFalse(ok)
        self.assertIn("Bus conflicts detected", msg)

if __name__ == "__main__":
    unittest.main()
