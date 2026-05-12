#!/usr/bin/env python3
import unittest
import shutil
from pathlib import Path
import sys

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev", "misc"]:
        sys.path.append(str(REPO_ROOT / ".agent" / "scripts" / domain))

import lib.paths
import knowledge.knowledge_synergy; import sys; sys.modules['knowledge_synergy'] = sys.modules['knowledge.knowledge_synergy']; import knowledge.knowledge_synergy as knowledge_synergy

class TestKnowledgeSynergy(unittest.TestCase):
    def setUp(self):
        self.test_root = REPO_ROOT / "scratch" / "test_synergy"
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        # Override paths in lib.paths
        self.original_global = lib.paths.GLOBAL_LESSONS_PATH
        self.original_global_root = lib.paths.GLOBAL_ROOT
        
        lib.paths.GLOBAL_ROOT = self.test_root / "global"
        lib.paths.GLOBAL_LESSONS_PATH = lib.paths.GLOBAL_ROOT / "lessons_learned.md"
        knowledge_synergy.GLOBAL_ROOT = lib.paths.GLOBAL_ROOT
        knowledge_synergy.GLOBAL_LESSONS_PATH = lib.paths.GLOBAL_LESSONS_PATH

    def tearDown(self):
        lib.paths.GLOBAL_LESSONS_PATH = self.original_global
        lib.paths.GLOBAL_ROOT = self.original_global_root
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_export_adr(self):
        # Create a local ADR
        adr_path = self.test_root / "ADR-001-Test.md"
        adr_path.write_text("# Decision 1\nWe use Python.")
        
        knowledge_synergy.export_adr_to_global(adr_path)
        
        self.assertTrue(lib.paths.GLOBAL_LESSONS_PATH.exists())
        content = lib.paths.GLOBAL_LESSONS_PATH.read_text()
        self.assertIn("ADR-001-Test", content)
        self.assertIn("We use Python.", content)

if __name__ == "__main__":
    unittest.main()
