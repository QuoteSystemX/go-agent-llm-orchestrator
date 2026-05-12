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

import knowledge.obsidian_sync; import sys; sys.modules['obsidian_sync'] = sys.modules['knowledge.obsidian_sync']; import knowledge.obsidian_sync as obsidian_sync

class TestObsidianSync(unittest.TestCase):
    def setUp(self):
        self.test_root = REPO_ROOT / "scratch" / "test_obsidian"
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        # Mock repo structure
        self.knowledge_dir = self.test_root / ".agent" / "knowledge"
        self.knowledge_dir.mkdir(parents=True)
        (self.knowledge_dir / "test_ki.md").write_text("# Test Knowledge\nThis is a test [[TestSymbol]] link.")
        
        self.wiki_dir = self.test_root / "wiki"
        self.wiki_dir.mkdir(parents=True)
        (self.wiki_dir / "test_page.md").write_text("# Test Page\nReferencing [[test_ki]] and [[nonexistent]].")
        
        self.vault_dir = self.test_root / "vault"
        
        # Override REPO_ROOT in obsidian_sync (monkeypatching)
        self.original_root = obsidian_sync.REPO_ROOT
        obsidian_sync.REPO_ROOT = self.test_root
        obsidian_sync.WIKI_DIR = Path("wiki")
        obsidian_sync.MAP_FILE = Path(".agent/bus/wiki_map.json")

    def tearDown(self):
        obsidian_sync.REPO_ROOT = self.original_root
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_sync_links(self):
        obsidian_sync.sync_links()
        map_path = self.test_root / ".agent" / "bus" / "wiki_map.json"
        self.assertTrue(map_path.exists())
        
        with open(map_path) as f:
            data = json.load(f)
            self.assertIn("test_ki", data["map"])
            self.assertEqual(data["map"]["test_ki"]["mentions_in_wiki"], ["wiki/test_page.md"])

    def test_sync_to_obsidian(self):
        # Create config
        config_path = self.test_root / ".agent" / "config" / "obsidian_config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config = {
            "vault_path": str(self.vault_dir),
            "sync_folders": [".agent/knowledge", "wiki"],
            "auto_tag": True,
            "add_metadata": True
        }
        with open(config_path, "w") as f:
            json.dump(config, f)
            
        obsidian_sync.sync_to_obsidian()
        
        # Check if files are mirrored
        self.assertTrue((self.vault_dir / "knowledge" / "test_ki.md").exists())
        self.assertTrue((self.vault_dir / "wiki" / "test_page.md").exists())
        
        content = (self.vault_dir / "knowledge" / "test_ki.md").read_text()
        self.assertIn("synced_at:", content)
        self.assertIn("tags: [hive, knowledge, knowledge]", content)

if __name__ == "__main__":
    unittest.main()
