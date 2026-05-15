#!/usr/bin/env python3
import unittest
import shutil
import sys
import os
import json
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

import dev.output_bridge as bridge

class TestOutputBridge(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_output_bridge").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.bus_dir = self.test_root / ".agent" / "bus" / "outputs"
        self.bus_dir.mkdir(parents=True)
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)

    def tearDown(self):
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_validate_sections(self):
        content = "🤖 **Agent Header**\n🎯 **Context/Goal**\n🛠 **Technical Implementation**\n📂 **Impacted Components**\n📈 **Outcome/Result**"
        missing = bridge.validate_sections(content)
        self.assertEqual(len(missing), 0)
        
        content_missing = "🤖 **Agent Header**"
        missing = bridge.validate_sections(content_missing)
        self.assertGreater(len(missing), 0)

    @patch('sys.exit')
    def test_save_to_bus_logic(self, mock_exit):
        content = """
🤖 **Agent Header**: coder
🎯 **Context/Goal**: fix bug in auth
🛠 **Technical Implementation**: changed auth.py
📂 **Impacted Components**: file:///auth.py
📈 **Outcome/Result**: verified
"""
        # Ensure directory exists in test_root
        os.makedirs(self.bus_dir, exist_ok=True)
        bridge.save_to_bus(content, "coder")
        
        # Check the file created
        files = list(self.bus_dir.glob("*.json"))
        self.assertEqual(len(files), 1)
        written_data = json.loads(files[0].read_text())
        self.assertEqual(written_data["agent"], "coder")
        self.assertEqual(written_data["goal"], "fix bug in auth")
        self.assertIn("auth.py", written_data["impacted_files"])

    @patch('subprocess.run')
    def test_synthesize_outputs(self, mock_run):
        # Create dummy outputs
        os.makedirs(self.bus_dir, exist_ok=True)
        (self.bus_dir / "1.json").write_text(json.dumps({"agent": "a1", "goal": "g1", "impacted_files": ["f1"]}))
        (self.bus_dir / "2.json").write_text(json.dumps({"agent": "a2", "goal": "g2", "impacted_files": ["f2"]}))
        
        with patch('sys.stdout', new=MagicMock()):
            bridge.synthesize_outputs()
            
        # Verify automation scripts were "called" (mocked)
        self.assertGreater(mock_run.call_count, 0)
        # Verify bus was cleared
        self.assertEqual(len(list(self.bus_dir.glob("*.json"))), 0)

    @patch('sys.stdin.read')
    @patch('sys.exit')
    def test_main_validation_failure(self, mock_exit, mock_read):
        mock_read.return_value = "Invalid content"
        # Avoid subprocess calls during main
        with patch('subprocess.run'):
            bridge.main()
        mock_exit.assert_called_with(1)

if __name__ == "__main__":
    unittest.main()
