#!/usr/bin/env python3
import unittest
import sys
import os
import shutil
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

import analysis.post_mortem_runner as pm

class TestPostMortemRunner(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_post_mortem").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.bus_dir = self.test_root / ".agent" / "bus"
        self.bus_dir.mkdir(parents=True)
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)
        
        self.patch_bus = patch('analysis.post_mortem_runner.BUS_DIR', self.bus_dir)
        self.patch_bus.start()

    def tearDown(self):
        self.patch_bus.stop()
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_run_post_mortem_no_bus(self):
        result = pm.run_post_mortem()
        self.assertEqual(result, "No bus data for post-mortem.")

    def test_run_post_mortem(self):
        bus_file = self.bus_dir / "context.json"
        events = [
            {"type": "error", "author": "orchestrator", "id": "1"},
            {"type": "recovery", "author": "self-healer", "id": "2"}
        ]
        bus_file.write_text(json.dumps({"objects": events}))
        
        result = pm.run_post_mortem()
        
        self.assertIn("Post-Mortem Report", result)
        self.assertIn("```mermaid", result)
        self.assertIn("self_healer->>Bus: Push recovery", result)
        self.assertIn("- Last Agent active: self-healer", result)

if __name__ == "__main__":
    unittest.main()
