#!/usr/bin/env python3
import unittest
import shutil
import sys
import os
import re
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

import knowledge.generate_adr as generator

class TestGenerateADR(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_generate_adr").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.adr_dir = self.test_root / "wiki" / "decisions"
        self.adr_dir.mkdir(parents=True)
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)
        
        # Patch paths in generator
        self.patch_root = patch('knowledge.generate_adr.REPO_ROOT', self.test_root)
        self.patch_adr_dir = patch('knowledge.generate_adr.ADR_DIR', self.adr_dir)
        
        self.patch_root.start()
        self.patch_adr_dir.start()

    def tearDown(self):
        self.patch_root.stop()
        self.patch_adr_dir.stop()
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_generate_adr(self):
        title = "Adopt Micro-Frontends"
        context = "The frontend is too monolithic."
        decision = "We will use module federation."
        
        result = generator.generate_adr(title, context, decision)
        self.assertIn("ADR created", result)
        
        expected_path = self.adr_dir / "ADR-001-adopt-micro-frontends.md"
        self.assertTrue(expected_path.exists())
        
        content = expected_path.read_text()
        self.assertIn("# ADR-001: Adopt Micro-Frontends", content)
        self.assertIn(context, content)
        self.assertIn(decision, content)

    def test_generate_adr_increment(self):
        # Pre-create an ADR
        (self.adr_dir / "ADR-005-existing.md").write_text("existing")
        
        result = generator.generate_adr("New Decision", "C", "D")
        self.assertIn("ADR-006", result)
        self.assertTrue((self.adr_dir / "ADR-006-new-decision.md").exists())

    @patch('sys.exit')
    @patch('sys.argv', ['generate_adr.py', 'Title', 'Context', 'Decision'])
    def test_main(self, mock_exit):
        with patch('sys.stdout', new=MagicMock()):
            generator.main()
        
        self.assertTrue(list(self.adr_dir.glob("ADR-*.md")))

if __name__ == "__main__":
    unittest.main()
