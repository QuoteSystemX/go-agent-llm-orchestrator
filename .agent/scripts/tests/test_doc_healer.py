#!/usr/bin/env python3
import unittest
from unittest.mock import patch, MagicMock
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

import dev.doc_healer; import sys; sys.modules['doc_healer'] = sys.modules['dev.doc_healer']; import dev.doc_healer as doc_healer

class TestDocHealer(unittest.TestCase):
    def setUp(self):
        self.test_root = REPO_ROOT / "scratch" / "test_healer"
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        # Override REPO_ROOT in doc_healer
        self.original_root = doc_healer.REPO_ROOT
        doc_healer.REPO_ROOT = self.test_root
        
        # Mock ARCHITECTURE.md
        self.arch_path = self.test_root / ".agent" / "ARCHITECTURE.md"
        self.arch_path.parent.mkdir(parents=True)
        self.arch_path.write_text("# Architecture\n\nExisting content.")
        
        # Mock a "drifted" file
        self.new_file = self.test_root / "new_script.py"
        self.new_file.write_text('"""Test Script — Does something cool."""\nprint("hello")')

    def tearDown(self):
        doc_healer.REPO_ROOT = self.original_root
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    @patch("drift_detector.detect_drift")
    @patch("visualize_deps.generate_mermaid")
    def test_heal_docs(self, mock_mermaid, mock_drift):
        mock_drift.return_value = ["FILE DRIFT: new_script.py (modified but not in docs)"]
        mock_mermaid.return_value = "graph TD\n"
        
        res = doc_healer.heal_docs()
        
        self.assertIn("✅ Documentation healing complete.", res)
        content = self.arch_path.read_text()
        self.assertIn("## 🆕 Recent Additions", content)
        self.assertIn("`new_script.py`", content)
        self.assertIn("Test Script — Does something cool.", content)

if __name__ == "__main__":
    unittest.main()
