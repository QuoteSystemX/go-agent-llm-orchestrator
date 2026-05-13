#!/usr/bin/env python3
import unittest
import sys
import os
import shutil
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

import misc.generate_discovery_files as discovery

class TestGenerateDiscoveryFiles(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_discovery").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)
        
        self.patch_wiki = patch('misc.generate_discovery_files.WIKI_DIR', self.test_root / "wiki")
        self.patch_wiki.start()

    def tearDown(self):
        self.patch_wiki.stop()
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_generate_sitemap(self):
        # Create some files
        wiki_dir = self.test_root / "wiki"
        wiki_dir.mkdir()
        (wiki_dir / "page1.md").write_text("test")
        (self.test_root / "index.html").write_text("html")
        
        with patch('sys.stdout', new=MagicMock()):
            discovery.generate_sitemap()
            
        sitemap_path = self.test_root / "sitemap.xml"
        self.assertTrue(sitemap_path.exists())
        content = sitemap_path.read_text()
        self.assertIn("page1", content)
        self.assertIn("index.html", content)
        self.assertIn("<loc>", content)

    def test_generate_robots(self):
        with patch('sys.stdout', new=MagicMock()):
            discovery.generate_robots()
            
        robots_path = self.test_root / "robots.txt"
        self.assertTrue(robots_path.exists())
        content = robots_path.read_text()
        self.assertIn("User-agent: *", content)
        self.assertIn("Allow: /", content)
        self.assertIn("sitemap.xml", content)

if __name__ == "__main__":
    unittest.main()
