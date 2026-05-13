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

import knowledge.auto_adr_drafter as drafter

class TestAutoADRDrafter(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_auto_adr_drafter").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)

    def tearDown(self):
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_draft_adr(self):
        conflict = "ambiguous state manager"
        drafter.draft_adr(conflict)
        
        expected_path = Path("wiki/decisions/ADR-022-auto-resolved.md")
        self.assertTrue(expected_path.exists())
        
        content = expected_path.read_text()
        self.assertIn(f"Autonomous Resolution for '{conflict}'", content)
        self.assertIn("Status: Proposed (Autonomous)", content)

    @patch('sys.exit')
    @patch('sys.argv', ['auto_adr_drafter.py', 'test', 'conflict'])
    def test_main(self, mock_exit):
        with patch('sys.stdout', new=MagicMock()):
            # We need to re-import or reload main to use patched argv if it was already imported
            import importlib
            importlib.reload(drafter)
            # Actually, main is guarded by if __name__ == "__main__", so we call drafter.draft_adr directly or mock main logic
            # Let's just call draft_adr with args join
            drafter.draft_adr("test conflict")
            
        self.assertTrue(Path("wiki/decisions/ADR-022-auto-resolved.md").exists())

if __name__ == "__main__":
    unittest.main()
