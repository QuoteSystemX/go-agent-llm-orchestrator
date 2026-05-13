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

import dev.doc_healer as healer

class TestDocHealer(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_doc_healer").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.arch_file = self.test_root / ".agent" / "ARCHITECTURE.md"
        self.arch_file.parent.mkdir(parents=True)
        self.arch_file.write_text("# Architecture\nExisting docs.")
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)
        
        # Patch REPO_ROOT in healer
        self.patch_root = patch('dev.doc_healer.REPO_ROOT', self.test_root)
        self.patch_root.start()

    def tearDown(self):
        self.patch_root.stop()
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    @patch('drift_detector.detect_drift')
    @patch('visualize_deps.generate_mermaid', return_value="graph TD")
    def test_heal_docs_python(self, mock_mermaid, mock_drift):
        # Create a "new" file with a docstring
        new_file = self.test_root / "new_module.py"
        new_file.write_text('"""This is a test module."""\nprint("hello")')
        
        mock_drift.return_value = ["FILE DRIFT: new_module.py (not in docs)"]
        
        result = healer.heal_docs()
        self.assertIn("Documentation healing complete", result)
        
        content = self.arch_file.read_text()
        self.assertIn("## 🆕 Recent Additions", content)
        self.assertIn("`new_module.py`", content)
        self.assertIn("This is a test module.", content)

    @patch('drift_detector.detect_drift')
    @patch('visualize_deps.generate_mermaid', return_value="graph TD")
    def test_heal_docs_go(self, mock_mermaid, mock_drift):
        # Create a "new" file with // comments
        new_file = self.test_root / "new_module.go"
        new_file.write_text('// Package test provides testing utilities.\npackage test')
        
        mock_drift.return_value = ["FILE DRIFT: new_module.go (not in docs)"]
        
        healer.heal_docs()
        
        content = self.arch_file.read_text()
        self.assertIn("Package test provides testing utilities.", content)

    @patch('drift_detector.detect_drift', return_value=[])
    def test_no_drift(self, mock_drift):
        result = healer.heal_docs()
        self.assertIn("No file drift detected", result)

if __name__ == "__main__":
    unittest.main()
