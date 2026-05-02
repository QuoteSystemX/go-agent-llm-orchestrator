#!/usr/bin/env python3
import os
import unittest
from pathlib import Path
import shutil
import sys
import importlib

# Ensure we can import from scripts
sys.path.append(str(Path(__file__).resolve().parent.parent))

from lib.paths import GLOBAL_ROOT, GLOBAL_LESSONS_PATH
import knowledge_synergy
import experience_distiller

class TestGlobalBrain(unittest.TestCase):
    def setUp(self):
        # Setup fake global root
        self.fake_global = Path("/tmp/fake_agent_knowledge")
        if self.fake_global.exists():
            shutil.rmtree(self.fake_global)
        self.fake_global.mkdir(parents=True)
        
        # Set env var
        os.environ["AGENT_GLOBAL_ROOT"] = str(self.fake_global)
        
        # Reload modules to apply env var change
        import importlib
        import lib.paths
        importlib.reload(lib.paths)
        importlib.reload(knowledge_synergy)
        importlib.reload(experience_distiller)
        
        self.global_root = lib.paths.GLOBAL_ROOT
        self.global_lessons = lib.paths.GLOBAL_LESSONS_PATH

    def tearDown(self):
        if self.fake_global.exists():
            shutil.rmtree(self.fake_global)

    def test_01_path_resolution(self):
        """Verify GLOBAL_ROOT follows env var."""
        self.assertEqual(str(self.global_root), str(self.fake_global))

    def test_02_adr_export(self):
        """Verify local ADR can be exported to global lessons."""
        fake_adr = Path("/tmp/ADR-TEST-99.md")
        fake_adr.write_text("# Decision: Use Rust\nBecause it is fast.", encoding="utf-8")
        
        knowledge_synergy.export_adr_to_global(fake_adr)
        
        self.assertTrue(self.global_lessons.exists())
        content = self.global_lessons.read_text(encoding="utf-8")
        self.assertIn("ADR-TEST-99", content)
        self.assertIn("Use Rust", content)
        
        if fake_adr.exists(): fake_adr.unlink()

    def test_03_global_search(self):
        """Verify experience_distiller searches global lessons."""
        # 1. Create global lesson
        self.global_lessons.write_text("### [2026-05-01] [FEAT] [rust-pro] Shared Global Wisdom\nAlways use cargo-deny.", encoding="utf-8")
        
        # 2. Search using distiller
        importlib.reload(experience_distiller)
        result = experience_distiller.search_lessons("Wisdom")
        
        self.assertIn("Shared Global Wisdom", result)
        self.assertIn("Top", result)

if __name__ == "__main__":
    unittest.main()
