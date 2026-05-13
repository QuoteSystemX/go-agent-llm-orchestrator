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

import dev.skill_factory as factory

class TestSkillFactory(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_factory_unit").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.scripts_dir = self.test_root / ".agent" / "scripts"
        self.scripts_dir.mkdir(parents=True)
        self.tests_dir = self.test_root / ".agent" / "tests"
        # factory.py uses REPO_ROOT / ".agent" / "tests"
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)
        
        # Patch REPO_ROOT
        self.patch_root = patch('dev.skill_factory.REPO_ROOT', self.test_root)
        self.patch_root.start()

    def tearDown(self):
        self.patch_root.stop()
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_create_python_script(self):
        success = factory.create_script("new_tool.py", "A test tool")
        self.assertTrue(success)
        
        script_path = self.scripts_dir / "new_tool.py"
        self.assertTrue(script_path.exists())
        self.assertTrue(os.access(script_path, os.X_OK))
        
        test_path = self.test_root / ".agent" / "tests" / "test_new_tool.py"
        self.assertTrue(test_path.exists())
        
        content = script_path.read_text()
        self.assertIn("A test tool", content)

    def test_create_go_script(self):
        # Create a subdir for go package name detection
        go_dir = self.scripts_dir / "internal"
        go_dir.mkdir()
        
        # Patch scripts_dir for this test
        with patch('dev.skill_factory.REPO_ROOT', self.test_root):
            # The script uses REPO_ROOT / ".agent" / "scripts"
            # We need to target the internal dir
            # factory.py: target_path = scripts_dir / name
            # If name has subdirs, it works.
            success = factory.create_script("internal/engine.go", "Go engine")
            
        self.assertTrue(success)
        script_path = go_dir / "engine.go"
        self.assertTrue(script_path.exists())
        
        test_path = go_dir / "engine_test.go"
        self.assertTrue(test_path.exists())
        content = test_path.read_text()
        self.assertIn("package internal", content)

    def test_duplicate_script(self):
        script_path = self.scripts_dir / "dup.py"
        script_path.write_text("exists")
        
        success = factory.create_script("dup.py", "wont work")
        self.assertFalse(success)

if __name__ == "__main__":
    unittest.main()
