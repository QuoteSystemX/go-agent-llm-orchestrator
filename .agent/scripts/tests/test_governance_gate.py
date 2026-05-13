#!/usr/bin/env python3
import unittest
import json
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

import orchestration.governance_gate as gate

class TestGovernanceGate(unittest.TestCase):
    def setUp(self):
        self.test_root = REPO_ROOT / "scratch" / "test_governance"
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.patch_repo = patch('orchestration.governance_gate.REPO_ROOT', self.test_root)
        self.patch_wiki_stories = patch('orchestration.governance_gate.WIKI_STORIES', self.test_root / "wiki/stories")
        self.patch_wiki_adr = patch('orchestration.governance_gate.WIKI_ADR', self.test_root / "wiki/decisions")
        
        self.patch_repo.start()
        self.patch_wiki_stories.start()
        self.patch_wiki_adr.start()

    def tearDown(self):
        self.patch_repo.stop()
        self.patch_wiki_stories.stop()
        self.patch_wiki_adr.stop()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_is_file_in_wiki_found(self):
        stories_dir = self.test_root / "wiki/stories"
        stories_dir.mkdir(parents=True)
        (stories_dir / "story1.md").write_text("Implementing new_feature.py")
        
        self.assertTrue(gate.is_file_in_wiki("new_feature.py"))

    def test_is_file_in_wiki_not_found(self):
        self.assertFalse(gate.is_file_in_wiki("missing.py"))

    @patch('orchestration.governance_gate.run_auditor')
    def test_check_governance_new_file_blocked(self, mock_audit):
        mock_audit.return_value = (True, "OK")
        # File doesn't exist, and not in wiki
        success = gate.check_governance(["new_file.py"])
        self.assertFalse(success)

    @patch('orchestration.governance_gate.run_auditor')
    def test_check_governance_policy_violation(self, mock_audit):
        # File exists and in wiki, but policy guardrail fails
        (self.test_root / "wiki/stories").mkdir(parents=True)
        (self.test_root / "wiki/stories/s1.md").write_text("existing_file.py")
        (self.test_root / "existing_file.py").write_text("content")
        
        # policy_guardrail fails
        mock_audit.side_effect = [(True, "OK"), (False, "Violation!")]
        
        success = gate.check_governance(["existing_file.py"])
        self.assertFalse(success)

    @patch('orchestration.governance_gate.run_auditor')
    def test_check_governance_success(self, mock_audit):
        (self.test_root / "wiki/stories").mkdir(parents=True)
        (self.test_root / "wiki/stories/s1.md").write_text("ok_file.py")
        (self.test_root / "ok_file.py").write_text("content")
        
        mock_audit.return_value = (True, "OK")
        
        success = gate.check_governance(["ok_file.py"])
        self.assertTrue(success)

if __name__ == "__main__":
    unittest.main()
