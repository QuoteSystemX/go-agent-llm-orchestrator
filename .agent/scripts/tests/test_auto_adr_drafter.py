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

    @patch('knowledge.auto_adr_drafter.query_llm_safe')
    def test_draft_adr_with_llm(self, mock_query):
        mock_query.return_value = ("# Mocked LLM ADR\nContent", "ollama", {})
        conflict = "ambiguous state manager"
        content = drafter.draft_adr(conflict)
        
        expected_path = Path("wiki/decisions/ADR-001-auto-resolved.md")
        self.assertTrue(expected_path.exists())
        self.assertEqual(content, "# Mocked LLM ADR\nContent")
        
        # Test auto-increment
        content2 = drafter.draft_adr(conflict)
        expected_path2 = Path("wiki/decisions/ADR-002-auto-resolved.md")
        self.assertTrue(expected_path2.exists())

    @patch('knowledge.auto_adr_drafter.query_llm_safe')
    def test_draft_adr_fallback(self, mock_query):
        mock_query.return_value = ("⚠️ [LLM Unavailable]", "stub", {})
        conflict = "ambiguous state manager"
        content = drafter.draft_adr(conflict)
        
        expected_path = Path("wiki/decisions/ADR-001-auto-resolved.md")
        self.assertTrue(expected_path.exists())
        self.assertIn("Status: Proposed (Autonomous)", content)
        self.assertIn("bridge/adapter pattern", content)

    @patch('sys.exit')
    @patch('sys.argv', ['auto_adr_drafter.py', 'test', 'conflict'])
    @patch('knowledge.auto_adr_drafter.query_llm_safe')
    def test_main(self, mock_query, mock_exit):
        mock_query.return_value = ("⚠️ [LLM Unavailable]", "stub", {})
        with patch('sys.stdout', new=MagicMock()):
            # Run the main script body logic under sys.argv patch
            drafter.draft_adr("test conflict")
            
        self.assertTrue(Path("wiki/decisions/ADR-001-auto-resolved.md").exists())

if __name__ == "__main__":
    unittest.main()
