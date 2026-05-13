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

import models.model_validator as validator

class TestModelValidator(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_model_validator").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.wiki_dir = self.test_root / "wiki" / "mental-models"
        self.wiki_dir.mkdir(parents=True)
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)
        
        # Patch paths
        self.patch_wiki = patch('models.model_validator.WIKI_DIR', self.wiki_dir)
        self.patch_wiki.start()

    def tearDown(self):
        self.patch_wiki.stop()
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_validate_change_success(self):
        (self.wiki_dir / "resilience.md").write_text("# Resilience-First\nBe safe.")
        success = validator.validate_change("Add logging", ["logger.py"])
        self.assertTrue(success)

    def test_validate_change_violation(self):
        (self.wiki_dir / "resilience.md").write_text("# Resilience-First\nBe safe.")
        with patch('sys.stdout', new=MagicMock()):
            success = validator.validate_change("Delete all files", ["main.py"])
        self.assertFalse(success)

    def test_load_mental_models(self):
        (self.wiki_dir / "model1.md").write_text("content1")
        (self.wiki_dir / "sub" / "model2.md").parent.mkdir()
        (self.wiki_dir / "sub" / "model2.md").write_text("content2")
        
        models = validator.load_mental_models()
        self.assertEqual(len(models), 2)
        self.assertIn("content1", models)
        self.assertIn("content2", models)

    @patch('sys.exit')
    @patch('sys.argv', ['model_validator.py', 'Add test', '["test.py"]'])
    def test_main(self, mock_exit):
        with patch('sys.stdout', new=MagicMock()):
            validator.main()
        mock_exit.assert_called_with(0)

if __name__ == "__main__":
    unittest.main()
