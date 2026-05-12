#!/usr/bin/env python3
import unittest
import os
import shutil
import json
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

import knowledge.promote_proposals; import sys; sys.modules['promote_proposals'] = sys.modules['knowledge.promote_proposals']; import knowledge.promote_proposals as promote_proposals

class TestPromoteProposals(unittest.TestCase):
    def setUp(self):
        self.test_root = REPO_ROOT / "scratch" / "test_proposals"
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        # Mock structure
        self.docs_dir = self.test_root / "docs" / "proposals"
        self.docs_dir.mkdir(parents=True)
        (self.docs_dir / "PROPOSAL-001-TEST.md").write_text("# Proposal 1\nStatus: Active\nContent here.")
        (self.docs_dir / "PROPOSAL-002-DRAFT.md").write_text("# Proposal 2\nStatus: Draft\nShould not be promoted.")
        
        self.knowledge_dir = self.test_root / ".agent" / "knowledge" / "decisions"
        self.knowledge_dir.mkdir(parents=True)
        
        # Override
        self.original_root = promote_proposals.REPO_ROOT
        promote_proposals.REPO_ROOT = self.test_root

    def tearDown(self):
        promote_proposals.REPO_ROOT = self.original_root
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_promote(self):
        promote_proposals.promote_active_proposals()
        
        # Check promotion
        self.assertTrue((self.knowledge_dir / "PROPOSAL-001-TEST.md").exists())
        self.assertFalse((self.knowledge_dir / "PROPOSAL-002-DRAFT.md").exists())
        
        content = (self.knowledge_dir / "PROPOSAL-001-TEST.md").read_text()
        self.assertIn("# Proposal 1", content)

if __name__ == "__main__":
    unittest.main()
