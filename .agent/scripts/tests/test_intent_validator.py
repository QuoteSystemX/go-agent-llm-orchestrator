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

import analysis.intent_validator as iv

class TestIntentValidator(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_intent").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.agent_dir = self.test_root / ".agent"
        self.agent_dir.mkdir()
        self.wiki_dir = self.test_root / "wiki" / "decisions"
        self.wiki_dir.mkdir(parents=True)
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)
        
        # Patch REPO_ROOT
        self.patch_root = patch('analysis.intent_validator.REPO_ROOT', self.test_root)
        self.patch_root.start()

    def tearDown(self):
        self.patch_root.stop()
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_validate_intent_conflict(self):
        # Establish standard in ARCHITECTURE.md
        (self.agent_dir / "ARCHITECTURE.md").write_text("Database: PostgreSQL")
        
        # Intent uses MongoDB
        conflicts = iv.validate_intent("Use MongoDB for storage")
        
        self.assertTrue(any("uses 'mongodb'" in c for c in conflicts))
        self.assertTrue(any("uses ['postgresql']" in c for c in conflicts))

    def test_validate_intent_consistent(self):
        (self.agent_dir / "ARCHITECTURE.md").write_text("Language: Go")
        
        conflicts = iv.validate_intent("Add a new Go service")
        self.assertEqual(len(conflicts), 0)

    def test_validate_intent_new_tech(self):
        # Empty context
        (self.agent_dir / "ARCHITECTURE.md").write_text("Minimal arch")
        
        conflicts = iv.validate_intent("Implement with Rust")
        self.assertTrue(any("New technology 'rust' detected" in c for c in conflicts))

if __name__ == "__main__":
    unittest.main()
