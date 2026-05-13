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

import delivery.social_proof_generator as spg

class TestSocialProofGenerator(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_social_proof").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        self.snapshot_dir = self.test_root / "docs" / "snapshots"
        self.snapshot_dir.mkdir(parents=True)
        self.wiki_dir = self.test_root / "wiki"
        self.wiki_dir.mkdir()
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)
        
        # Patch paths
        self.patch_root = patch('delivery.social_proof_generator.SNAPSHOT_DIR', self.snapshot_dir)
        self.patch_wiki = patch('delivery.social_proof_generator.WIKI_DIR', self.wiki_dir)
        self.patch_root.start()
        self.patch_wiki.start()

    def tearDown(self):
        self.patch_root.stop()
        self.patch_wiki.stop()
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_extract_wins(self):
        (self.snapshot_dir / "snap1.md").write_text("- **Feature X** – Successfully deployed to prod")
        
        wins = spg.extract_wins()
        self.assertTrue(any(w["title"] == "Feature X" for w in wins))
        self.assertTrue(any("Successfully deployed" in w["description"] for w in wins))

    def test_generate_report(self):
        wins = [{"title": "Win1", "description": "Desc1"}]
        spg.generate_report(wins)
        
        report_file = self.wiki_dir / "RECENT_WINS.md"
        self.assertTrue(report_file.exists())
        content = report_file.read_text()
        self.assertIn("Win1", content)
        self.assertIn("Desc1", content)

if __name__ == "__main__":
    unittest.main()
