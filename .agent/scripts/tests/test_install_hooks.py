#!/usr/bin/env python3
import unittest
import shutil
import sys
import os
import stat
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

import dev.install_hooks as install_hooks

class TestInstallHooks(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_install_hooks").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)
        
        self.patch_root = patch('dev.install_hooks.REPO_ROOT', self.test_root)
        self.patch_root.start()

    def tearDown(self):
        self.patch_root.stop()
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_install_pre_commit_no_git(self):
        with patch('sys.stdout', new=MagicMock()):
            result = install_hooks.install_pre_commit()
        self.assertFalse(result)

    def test_install_pre_commit_success(self):
        hooks_dir = self.test_root / ".git" / "hooks"
        hooks_dir.mkdir(parents=True)
        
        with patch('sys.stdout', new=MagicMock()):
            result = install_hooks.install_pre_commit()
            
        self.assertTrue(result)
        hook_path = hooks_dir / "pre-commit"
        self.assertTrue(hook_path.exists())
        self.assertIn("pre_commit_review.py", hook_path.read_text())
        
        # Verify executable permissions
        st = os.stat(hook_path)
        self.assertTrue(st.st_mode & stat.S_IXUSR)

if __name__ == "__main__":
    unittest.main()
