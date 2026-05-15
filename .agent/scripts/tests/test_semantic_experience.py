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

import models.semantic_experience as semantic

class TestSemanticExperience(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_semantic_experience").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.wiki_dir = self.test_root / "wiki"
        self.wiki_dir.mkdir(parents=True)
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)
        
        self.patch_root = patch('models.semantic_experience.REPO_ROOT', self.test_root)
        self.patch_root.start()

    def tearDown(self):
        self.patch_root.stop()
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_search_semantic_no_file(self):
        result = semantic.search_semantic("test query")
        self.assertEqual(result, "No experience base found.")

    def test_search_semantic_no_matches(self):
        (self.wiki_dir / "LESSONS_LEARNED.md").write_text("### Topic\nNothing here.")
        result = semantic.search_semantic("test query")
        self.assertEqual(result, "No semantic matches for 'test query'.")

    def test_search_semantic_matches(self):
        content = "Intro\n### Auth System\nWe built an auth system.\n### Metrics System\nWe built a metrics system for auth."
        (self.wiki_dir / "LESSONS_LEARNED.md").write_text(content)
        
        # 'auth system' -> 'auth' and 'system'
        # Auth System block: 'built', 'an', 'auth', 'system.' -> 2 matches
        # Metrics System block: 'built', 'a', 'metrics', 'system', 'for', 'auth.' -> 2 matches
        # Wait, 'system.' vs 'system'. The script uses replace('`', '').replace('|', '').split()
        # So 'system.' is one word. 'auth.' is another.
        # Let's change the query to exactly match words.
        
        # Let's query "auth system"
        # In "Auth System", words are "auth", "system" (from title), "we", "built", "an", "auth", "system."
        # overlap = 2
        
        result = semantic.search_semantic("auth system")
        self.assertIn("Best Contextual Match", result)
        self.assertIn("Auth System", result)

    @patch('sys.argv', ['semantic_experience.py', 'auth', 'system'])
    def test_main_with_args(self):
        content = "### Auth System\nWe built an auth system."
        (self.wiki_dir / "LESSONS_LEARNED.md").write_text(content)
        with patch('sys.stdout', new=MagicMock()) as mock_out:
            import runpy
            with patch.dict('sys.modules', {'models.semantic_experience': semantic}):
                semantic.search_semantic("auth system")

if __name__ == "__main__":
    unittest.main()
