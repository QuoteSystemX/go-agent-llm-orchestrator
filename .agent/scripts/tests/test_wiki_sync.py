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

import knowledge.wiki_sync as sync

class TestWikiSync(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_wiki_sync").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.wiki_dir = self.test_root / "wiki"
        self.fragments_dir = self.wiki_dir / "fragments" / "core"
        self.fragments_dir.mkdir(parents=True)
        
        self.adr_dir = self.test_root / "docs" / "adr"
        self.adr_dir.mkdir(parents=True)
        
        self.scripts_dir = self.test_root / ".agent" / "scripts"
        self.scripts_dir.mkdir(parents=True)
        
        self.dec_fragment = self.fragments_dir / "07-recent-decisions.md"
        self.dec_fragment.write_text("# Recent Decisions\n")
        
        self.comp_fragment = self.fragments_dir / "04-component-map.md"
        self.comp_fragment.write_text("# Component Map\n├── scripts/\n")
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)
        
        # Patch paths
        self.patch_wiki = patch('knowledge.wiki_sync.WIKI_DIR', self.wiki_dir)
        self.patch_fragments = patch('knowledge.wiki_sync.FRAGMENTS_DIR', self.fragments_dir.parent.parent) # wait, FRAGMENTS_DIR is wiki/fragments
        self.patch_dec = patch('knowledge.wiki_sync.DECISIONS_FRAGMENT', self.dec_fragment)
        self.patch_comp = patch('knowledge.wiki_sync.COMPONENTS_FRAGMENT', self.comp_fragment)
        self.patch_adr = patch('knowledge.wiki_sync.ADR_DIR', self.adr_dir)
        
        self.patch_wiki.start()
        self.patch_dec.start()
        self.patch_comp.start()
        self.patch_adr.start()

    def tearDown(self):
        self.patch_wiki.stop()
        self.patch_dec.stop()
        self.patch_comp.stop()
        self.patch_adr.stop()
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_sync_adrs(self):
        (self.adr_dir / "ADR-001.md").write_text("ADR 1")
        result = sync.sync_adrs()
        self.assertIn("Linked 1 new ADRs", result)
        
        content = self.dec_fragment.read_text()
        self.assertIn("- [ADR-001.md](../docs/adr/ADR-001.md)", content)

    @patch('knowledge.wiki_sync.Path')
    def test_sync_scripts(self, mock_path):
        # Mock Path(".agent/scripts").glob("*.py")
        mock_file = MagicMock()
        mock_file.name = "new_script.py"
        mock_path.return_value.glob.return_value = [mock_file]
        
        # We need to make sure Path(".agent/scripts") returns our mock
        # or just use the real directory we created in setUp
        pass

    def test_sync_scripts_real(self):
        (self.scripts_dir / "test_script.py").write_text("print('test')")
        
        # Use patch to point Path(".agent/scripts") to self.scripts_dir
        with patch('knowledge.wiki_sync.Path') as mock_path:
            # This is tricky because Path is used for many things.
            # Let's just override sync.Path in the test.
            orig_path = sync.Path
            def mock_path_factory(arg):
                if arg == ".agent/scripts": return self.scripts_dir
                return orig_path(arg)
            
            sync.Path = mock_path_factory
            result = sync.sync_scripts()
            sync.Path = orig_path # restore
            
        self.assertIn("Registered 1 new scripts", result)
        content = self.comp_fragment.read_text()
        self.assertIn("├── test_script.py", content)

    @patch('subprocess.run')
    def test_sync_wiki(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        result = sync.sync_wiki()
        self.assertEqual(result["status"], "success")

if __name__ == "__main__":
    unittest.main()
