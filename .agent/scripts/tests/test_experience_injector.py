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

if str(REPO_ROOT / ".agent") not in sys.path:
    sys.path.append(str(REPO_ROOT / ".agent"))
if str(REPO_ROOT / ".agent" / "scripts") not in sys.path:
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))
if str(REPO_ROOT / ".agent" / "skills" / "experience-injector" / "scripts") not in sys.path:
    sys.path.append(str(REPO_ROOT / ".agent" / "skills" / "experience-injector" / "scripts"))

import inject_experience as injector

class TestExperienceInjector(unittest.TestCase):
    def setUp(self):
        # Reset cwd to REPO_ROOT to avoid FileNotFoundError from deleted dirs
        os.chdir(str(REPO_ROOT))
        
        self.test_root = (REPO_ROOT / "scratch" / "test_experience_injector").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.lessons_path = self.test_root / ".agent" / "rules" / "LESSONS_LEARNED.md"
        self.lessons_path.parent.mkdir(parents=True)
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)
        
        self.patch_lessons = patch('inject_experience.LESSONS_PATH', self.lessons_path)
        self.patch_lessons.start()

    def tearDown(self):
        self.patch_lessons.stop()
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_query_lessons(self):
        # Setup mock lessons
        content = """# Lessons Learned
## Active Lessons
### [2026-06-22] [codebase-memory-mcp] GLIBC issue
- Context: Ubuntu 22.04 issue
- Root Cause: GLIBC 2.38
- Prevention: Use portable release
"""
        self.lessons_path.write_text(content, encoding="utf-8")
        
        # Test query matching
        result = injector.query_lessons("codebase-memory-mcp", top_n=1)
        self.assertIn("Relevant Historical Experience", result)
        self.assertIn("codebase-memory-mcp", result)

    def test_inject_to_file(self):
        target_file = self.test_root / "task.md"
        target_file.write_text("---\ntitle: Task\n---\nTask content\n", encoding="utf-8")
        
        lesson_block = "> [!IMPORTANT]\n> ### Lessons\n> - Lesson 1\n"
        injector.inject_to_file(target_file, lesson_block)
        
        injected_content = target_file.read_text(encoding="utf-8")
        self.assertIn("Lessons", injected_content)
        self.assertTrue(injected_content.startswith("---\ntitle: Task\n---\n\n> [!IMPORTANT]"))

if __name__ == "__main__":
    unittest.main()
