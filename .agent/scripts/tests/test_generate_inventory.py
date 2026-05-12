#!/usr/bin/env python3
import unittest
import os
import shutil
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

import knowledge.generate_inventory; import sys; sys.modules['generate_inventory'] = sys.modules['knowledge.generate_inventory']; import knowledge.generate_inventory as generate_inventory

class TestGenerateInventory(unittest.TestCase):
    def setUp(self):
        self.test_root = REPO_ROOT / "scratch" / "test_inventory"
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        # Mock structure
        (self.test_root / "src").mkdir()
        (self.test_root / "src" / "main.py").write_text("print('hello')")
        (self.test_root / ".agent" / "knowledge").mkdir(parents=True)
        
        # Override
        self.original_root = generate_inventory.REPO_ROOT
        generate_inventory.REPO_ROOT = self.test_root

    def tearDown(self):
        generate_inventory.REPO_ROOT = self.original_root
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_generate(self):
        generate_inventory.generate_inventory()
        
        inventory_path = self.test_root / ".agent" / "knowledge" / "inventory.md"
        self.assertTrue(inventory_path.exists())
        
        content = inventory_path.read_text()
        self.assertIn("src/main.py", content)

if __name__ == "__main__":
    unittest.main()
