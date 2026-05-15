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

import knowledge.adr_generator as generator

class TestADRGenerator(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_adr_generator").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.decisions_dir = self.test_root / "wiki" / "decisions"
        self.template_path = self.test_root / ".agent" / "wiki-templates" / "DECISIONS.md"
        self.template_path.parent.mkdir(parents=True)
        self.template_path.write_text("# [Decision Title]\nDate: YYYY-MM-DD\nStatus: Proposed / Accepted / Deprecated\nAuthor: [agent or person]")
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)
        
        # Patch paths in generator
        self.patch_root = patch('knowledge.adr_generator.REPO_ROOT', self.test_root)
        self.patch_decisions = patch('knowledge.adr_generator.DECISIONS_DIR', self.decisions_dir)
        self.patch_template = patch('knowledge.adr_generator.TEMPLATE_PATH', self.template_path)
        
        self.patch_root.start()
        self.patch_decisions.start()
        self.patch_template.start()

    def tearDown(self):
        self.patch_root.stop()
        self.patch_decisions.stop()
        self.patch_template.stop()
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_slugify(self):
        self.assertEqual(generator.slugify("Test Decision!"), "test-decision")
        self.assertEqual(generator.slugify("Multiple   Spaces"), "multiple-spaces")

    def test_create_adr_draft(self):
        path, error = generator.create_adr_draft("new_module.py")
        self.assertIsNone(error)
        self.assertTrue(path.exists())
        
        content = path.read_text()
        self.assertIn("Architectural Change in new_module.py", content)
        self.assertIn("Antigravity Agent", content)

    @patch('sys.argv', ['adr_generator.py', '--file', 'my_component.go'])
    def test_main_file(self):
        with patch('sys.stdout', new=MagicMock()):
            generator.main()
        
        files = list(self.decisions_dir.glob("*.md"))
        self.assertEqual(len(files), 1)
        self.assertIn("my-component", files[0].name)

if __name__ == "__main__":
    unittest.main()
