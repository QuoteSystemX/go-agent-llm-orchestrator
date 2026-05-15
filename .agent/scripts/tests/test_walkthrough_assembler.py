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

import delivery.walkthrough_assembler as assembler

class TestWalkthroughAssembler(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_walkthrough").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.bus_dir = self.test_root / ".agent" / "bus" / "outputs"
        self.bus_dir.mkdir(parents=True)
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)
        
        # Patch paths
        self.patch_bus = patch('delivery.walkthrough_assembler.BUS_DIR', str(self.bus_dir))
        self.patch_bus.start()

    def tearDown(self):
        self.patch_bus.stop()
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_get_session_outputs(self):
        (self.bus_dir / "1.json").write_text(json.dumps({"goal": "g1"}))
        (self.bus_dir / "2.json").write_text(json.dumps({"goal": "g2"}))
        
        outputs = assembler.get_session_outputs()
        self.assertEqual(len(outputs), 2)
        self.assertEqual(outputs[0]["goal"], "g1")

    def test_format_entry(self):
        output = {
            "timestamp": "2026-05-13",
            "agent": "coder",
            "goal": "fix bug",
            "impacted_files": ["a.py"]
        }
        entry = assembler.format_entry(output)
        self.assertIn("[2026-05-13] coder", entry)
        self.assertIn("**Goal**: fix bug", entry)
        self.assertIn("`a.py`", entry)

    def test_update_walkthrough(self):
        # Sample output
        (self.bus_dir / "1.json").write_text(json.dumps({"agent": "test", "goal": "done"}))
        
        # Walkthrough file
        walk_file = self.test_root / "walkthrough.md"
        walk_file.write_text("# Walkthrough\nInitial content")
        
        with patch('delivery.walkthrough_assembler.WALKTHROUGH_PATH', str(walk_file)):
            assembler.update_walkthrough()
            
        content = walk_file.read_text()
        self.assertIn("## 📝 Session Activity Log", content)
        self.assertIn("test", content)
        self.assertIn("done", content)

if __name__ == "__main__":
    unittest.main()
