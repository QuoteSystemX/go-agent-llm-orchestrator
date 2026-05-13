#!/usr/bin/env python3
import unittest
import shutil
import sys
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev", "misc"]:
        sys.path.append(str(REPO_ROOT / ".agent" / "scripts" / domain))

import knowledge.experience_distiller as distiller

class TestExperienceDistiller(unittest.TestCase):
    def setUp(self):
        self.test_root = REPO_ROOT / "scratch" / "test_distiller"
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.lessons_path = self.test_root / "LESSONS_LEARNED.md"
        self.archive_dir = self.test_root / "wiki" / "archive" / "experience"
        self.global_lessons_path = self.test_root / "GLOBAL_LESSONS.md"
        
        self.patch_lessons = patch('knowledge.experience_distiller.LESSONS_PATH', self.lessons_path)
        self.patch_archive = patch('knowledge.experience_distiller.ARCHIVE_DIR', self.archive_dir)
        self.patch_global = patch('knowledge.experience_distiller.GLOBAL_LESSONS_PATH', self.global_lessons_path)
        self.patch_repo = patch('knowledge.experience_distiller.REPO_ROOT', self.test_root)
        
        self.patch_lessons.start()
        self.patch_archive.start()
        self.patch_global.start()
        self.patch_repo.start()

    def tearDown(self):
        self.patch_lessons.stop()
        self.patch_archive.stop()
        self.patch_global.stop()
        self.patch_repo.stop()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_parse_entries(self):
        content = "# Lessons\n\n### [2026-05-10] [PASS] [skill-1]\nEntry 1\n### [2026-05-11] [FAIL] [skill-2]\nEntry 2"
        header, lessons = distiller.parse_entries(content)
        self.assertEqual(header, "# Lessons\n")
        self.assertEqual(len(lessons), 2)
        self.assertIn("[2026-05-10]", lessons[0])

    def test_extract_date(self):
        self.assertEqual(distiller.extract_date("### [2026-05-10] content"), datetime(2026, 5, 10))
        self.assertIsNone(distiller.extract_date("no date"))

    def test_extract_skill_tag(self):
        self.assertEqual(distiller.extract_skill_tag("### [2026-05-10] [PASS] [go-patterns] content"), "go-patterns")
        self.assertIsNone(distiller.extract_skill_tag("no tag"))

    def test_distill_lessons(self):
        old_date = (datetime.now() - timedelta(days=40)).strftime("%Y-%m-%d")
        new_date = datetime.now().strftime("%Y-%m-%d")
        
        content = f"# Header\n\n### [{old_date}] [PASS] [skill-1]\nOld lesson\n### [{new_date}] [PASS] [skill-2]\nNew lesson"
        self.lessons_path.write_text(content)
        
        res = distiller.distill_lessons()
        
        self.assertIn("1 active, 1 archived", res)
        self.assertTrue(self.archive_dir.exists())
        self.assertTrue((self.archive_dir / f"{old_date}.md").exists())
        
        new_content = self.lessons_path.read_text()
        self.assertIn("New lesson", new_content)
        self.assertNotIn("Old lesson", new_content)

    def test_filter_by_skill(self):
        self.lessons_path.write_text("### [2026-05-12] [PASS] [skill-a]\nActive match")
        self.archive_dir.mkdir(parents=True)
        (self.archive_dir / "2026-05-01.md").write_text("### [2026-05-01] [PASS] [skill-a]\nArchived match")
        
        res = distiller.filter_by_skill("skill-a")
        self.assertIn("Found 2 lesson(s)", res)
        self.assertIn("Active match", res)
        self.assertIn("Archived match", res)

if __name__ == "__main__":
    unittest.main()
