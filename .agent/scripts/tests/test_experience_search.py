#!/usr/bin/env python3
import unittest
import shutil
import sys
import os
import json
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

import knowledge.experience_search as search

class TestExperienceSearch(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_experience_search").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.snap_dir = self.test_root / "docs" / "snapshots"
        self.snap_dir.mkdir(parents=True)
        
        self.adr_dir = self.test_root / "docs" / "adr"
        self.adr_dir.mkdir(parents=True)
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)
        
        # We need to patch Path inside experience_search to use our test root,
        # but since experience_search uses `Path('docs/snapshots')`, if we chdir it just works.

    def tearDown(self):
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_search_experience_snapshot(self):
        (self.snap_dir / "snap1.md").write_text("# Snap\n- **feature** - we added auth\n")
        
        result = search.search_experience("auth")
        self.assertEqual(result["term"], "auth")
        self.assertEqual(len(result["matches"]), 1)
        self.assertEqual(result["matches"][0]["type"], "snapshot")
        self.assertIn("- **feature** - we added auth", result["matches"][0]["snippet"])

    def test_search_experience_adr(self):
        (self.adr_dir / "ADR-001.md").write_text("# Decision\nWe use postgres for auth.")
        
        result = search.search_experience("postgres")
        self.assertEqual(len(result["matches"]), 1)
        self.assertEqual(result["matches"][0]["type"], "adr")
        self.assertEqual(result["matches"][0]["title"], "ADR 001")

    @patch('sys.exit', side_effect=SystemExit)
    @patch('sys.argv', ['experience_search.py'])
    def test_main_missing_arg(self, mock_exit):
        with patch('sys.stdout', new=MagicMock()):
            with self.assertRaises(SystemExit):
                search.main()
        mock_exit.assert_called_with(1)

    @patch('sys.exit')
    @patch('sys.argv', ['experience_search.py', 'testterm'])
    def test_main_success(self, mock_exit):
        with patch('sys.stdout', new=MagicMock()):
            search.main()
        mock_exit.assert_not_called()

if __name__ == "__main__":
    unittest.main()
