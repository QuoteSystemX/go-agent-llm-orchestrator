#!/usr/bin/env python3
import unittest
import shutil
import json
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

import knowledge.obsidian_sync as obsidian_sync

class TestObsidianSync(unittest.TestCase):
    def setUp(self):
        self.test_root = REPO_ROOT / "scratch" / "test_obsidian"
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.patch_repo = patch('knowledge.obsidian_sync.REPO_ROOT', self.test_root)
        self.patch_repo.start()

    def tearDown(self):
        self.patch_repo.stop()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_extract_obsidian_links(self):
        text = "Check [[MySymbol]] and [[OtherSymbol|Label]]"
        links = obsidian_sync.extract_obsidian_links(text)
        self.assertEqual(links, ["MySymbol", "OtherSymbol"])

    def test_find_symbol_in_code(self):
        # Create a mock code file
        (self.test_root / "internal").mkdir()
        code_file = self.test_root / "internal" / "logic.py"
        code_file.write_text("def my_func(): pass\nclass MyClass: pass")
        
        matches = obsidian_sync.find_symbol_in_code("my_func")
        self.assertIn("internal/logic.py", matches)
        
        matches = obsidian_sync.find_symbol_in_code("MyClass")
        self.assertIn("internal/logic.py", matches)

    def test_sync_links(self):
        (self.test_root / "wiki").mkdir()
        wiki_file = self.test_root / "wiki" / "doc.md"
        wiki_file.write_text("Referencing [[my_func]]")
        
        (self.test_root / "internal").mkdir(exist_ok=True)
        (self.test_root / "internal" / "logic.py").write_text("def my_func(): pass")
        
        obsidian_sync.sync_links()
        
        map_file = self.test_root / ".agent" / "bus" / "wiki_map.json"
        self.assertTrue(map_file.exists())
        data = json.loads(map_file.read_text())
        self.assertIn("my_func", data["map"])
        self.assertIn("internal/logic.py", data["map"]["my_func"]["resolved_code_paths"])

    def test_sync_to_obsidian(self):
        # Setup source
        source_dir = self.test_root / "wiki" / "mental-models"
        source_dir.mkdir(parents=True)
        (source_dir / "model1.md").write_text("Content of model1")
        
        vault_dir = self.test_root / "obsidian_vault"
        
        # Mock config
        config = {
            "vault_path": str(vault_dir),
            "sync_folders": ["wiki/mental-models"],
            "auto_tag": True,
            "add_metadata": True
        }
        config_path = self.test_root / ".agent" / "config" / "obsidian_config.json"
        config_path.parent.mkdir(parents=True)
        config_path.write_text(json.dumps(config))
        
        obsidian_sync.sync_to_obsidian()
        
        mirrored_file = vault_dir / "mental-models" / "model1.md"
        self.assertTrue(mirrored_file.exists())
        content = mirrored_file.read_text()
        self.assertIn("synced_at:", content)
        self.assertIn("Content of model1", content)
        self.assertIn("tags: [hive, knowledge, mental-models]", content)

if __name__ == "__main__":
    unittest.main()
