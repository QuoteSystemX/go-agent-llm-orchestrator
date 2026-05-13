#!/usr/bin/env python3
import unittest
import shutil
import sys
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

import knowledge.wiki_assembler as assembler

class TestWikiAssembler(unittest.TestCase):
    def setUp(self):
        self.test_root = REPO_ROOT / "scratch" / "test_wiki"
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.wiki_dir = self.test_root / "wiki"
        self.fragments_dir = self.wiki_dir / "fragments"
        self.local_dir = self.fragments_dir / "local"
        self.local_dir.mkdir(parents=True)
        
        self.patch_fragments = patch('knowledge.wiki_assembler.FRAGMENTS_BASE', self.fragments_dir)
        self.patch_local = patch('knowledge.wiki_assembler.LOCAL_APP_DIR', self.local_dir)
        
        self.patch_fragments.start()
        self.patch_local.start()

    def tearDown(self):
        self.patch_fragments.stop()
        self.patch_local.stop()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_get_local_fragments(self):
        (self.local_dir / "f1.md").write_text("Frag 1")
        (self.local_dir / "f2.md").write_text("Frag 2")
        
        out = assembler.get_local_fragments()
        self.assertIn("Frag 1", out)
        self.assertIn("Frag 2", out)
        self.assertIn("---", out)

    def test_resolve_fragment_spoke_skip(self):
        out = assembler.resolve_fragment("app/secrets", "spoke")
        self.assertIn("SKIPPED", out)
        
        (self.fragments_dir / "core.md").write_text("Core Content")
        out = assembler.resolve_fragment("core", "spoke")
        self.assertEqual(out, "Core Content")

    def test_assemble_wiki_full(self):
        template = self.wiki_dir / "template.md"
        template.write_text("Header\n<!-- @INJECT:core -->\nFooter")
        
        (self.fragments_dir / "core.md").write_text("Middle")
        
        output = self.wiki_dir / "final.md"
        assembler.assemble_wiki(template, output, "hub")
        
        content = output.read_text()
        self.assertEqual(content, "Header\nMiddle\nFooter")

    def test_assemble_wiki_local_injection(self):
        template = self.wiki_dir / "template.md"
        template.write_text("Start\n<!-- @INJECT:SPOKE_LOCAL_APP -->\nEnd")
        
        (self.local_dir / "local1.md").write_text("My Local")
        
        output = self.wiki_dir / "final.md"
        assembler.assemble_wiki(template, output, "spoke")
        
        content = output.read_text()
        self.assertIn("My Local", content)

if __name__ == "__main__":
    unittest.main()
