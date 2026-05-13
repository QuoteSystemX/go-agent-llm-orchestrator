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

import knowledge.semantic_brain_engine as brain

class TestSemanticBrainEngine(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_semantic_brain_engine").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.lessons_path = self.test_root / ".agent" / "rules" / "GLOBAL_LESSONS.md"
        self.lessons_path.parent.mkdir(parents=True)
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)
        
        self.patch_lessons = patch('knowledge.semantic_brain_engine.GLOBAL_LESSONS_PATH', self.lessons_path)
        self.patch_lessons.start()

    def tearDown(self):
        self.patch_lessons.stop()
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_preprocess(self):
        text = "Hello, World! Security 123."
        tokens = brain.preprocess(text)
        self.assertCountEqual(tokens, ["hello", "world", "security", "123"])

    def test_calculate_similarity(self):
        # Empty inputs
        self.assertEqual(brain.calculate_similarity([], ["a"]), 0.0)
        self.assertEqual(brain.calculate_similarity(["a"], []), 0.0)
        
        # Exact match
        score = brain.calculate_similarity(["a", "b"], ["a", "b"])
        self.assertGreater(score, 0)
        
        # Weighted match (security weight is 2.5)
        score_weighted = brain.calculate_similarity(["security"], ["security"])
        score_unweighted = brain.calculate_similarity(["hello"], ["hello"])
        self.assertGreater(score_weighted, score_unweighted)

    def test_search_lessons(self):
        content = "## Lesson 1\nHello world.\n## Lesson 2\nSecurity issue fixed."
        self.lessons_path.write_text(content)
        
        results = brain.search_lessons("security issue")
        # Actually preprocess("security issue") = ["security", "issue"]
        # Lesson 1 tokens: ["lesson", "1", "hello", "world"] -> similarity 0
        # Lesson 2 tokens: ["lesson", "2", "security", "issue", "fixed"] -> similarity > 0
        
        # So only Lesson 2 should match
        self.assertEqual(len(results), 1)
        self.assertIn("Security issue", results[0]["content"])
        self.assertGreater(results[0]["score"], 0)

    @patch('sys.exit')
    @patch('sys.argv', ['semantic_brain_engine.py', 'security'])
    def test_main_success(self, mock_exit):
        self.lessons_path.write_text("## Lesson 1\nSecurity auth bug.")
        with patch('sys.stdout', new=MagicMock()):
            brain.main()
        mock_exit.assert_not_called()

    @patch('sys.exit')
    @patch('sys.argv', ['semantic_brain_engine.py'])
    def test_main_missing_args(self, mock_exit):
        with patch('sys.stdout', new=MagicMock()):
            brain.main()
        mock_exit.assert_called_with(1)

if __name__ == "__main__":
    unittest.main()
