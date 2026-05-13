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

import knowledge.obsidian_validator as validator

class TestObsidianValidator(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_obsidian_validator").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.wiki_dir = self.test_root / "wiki"
        self.wiki_dir.mkdir(parents=True)
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)

    def tearDown(self):
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_broken_links(self):
        (self.wiki_dir / "Source.md").write_text("Check [[MissingFile]] and [[Target#Section|Alias]].")
        (self.wiki_dir / "Target.md").write_text("Hello.")
        
        with patch('sys.stdout', new=MagicMock()) as mock_out:
            validator.validate_obsidian_links()
            # Verify stdout calls
            output = "".join(call.args[0] for call in mock_out.write.call_args_list)
            self.assertIn("Broken Links Found", output)
            self.assertIn("[[MissingFile]] (Target missing)", output)
            self.assertNotIn("[[Target]] (Target missing)", output)

    def test_orphan_files(self):
        (self.wiki_dir / "Source.md").write_text("Hello.")
        (self.wiki_dir / "Orphan.md").write_text("No one links to me.")
        
        with patch('sys.stdout', new=MagicMock()) as mock_out:
            validator.validate_obsidian_links()
            output = "".join(call.args[0] for call in mock_out.write.call_args_list)
            self.assertIn("Orphan Files", output)
            self.assertIn("Orphan.md", output)

    def test_missing_wiki(self):
        shutil.rmtree(self.wiki_dir)
        with patch('sys.stdout', new=MagicMock()) as mock_out:
            validator.validate_obsidian_links()
            output = "".join(call.args[0] for call in mock_out.write.call_args_list)
            self.assertIn("Wiki directory not found", output)

if __name__ == "__main__":
    unittest.main()
