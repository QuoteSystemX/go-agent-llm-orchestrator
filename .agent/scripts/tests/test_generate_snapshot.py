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

import misc.generate_snapshot as snap

class TestGenerateSnapshot(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_generate_snapshot").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.bus_dir = self.test_root / ".agent" / "bus"
        self.bus_dir.mkdir(parents=True)
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)

    def tearDown(self):
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_run_snapshot(self):
        # Create high priority event
        (self.bus_dir / "high.json").write_text(json.dumps({
            "priority": 10,
            "type": "architectural_shift",
            "summary": "Moved to Go",
            "created_at": "2026-05-13"
        }))
        # Create low priority event
        (self.bus_dir / "low.json").write_text(json.dumps({
            "priority": 1,
            "type": "heartbeat",
            "summary": "Still alive"
        }))
        
        result = snap.run_snapshot()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["event_count"], 1)
        
        snapshot_file = Path(result["snapshot_file"])
        self.assertTrue(snapshot_file.exists())
        
        content = snapshot_file.read_text()
        self.assertIn("high.json", content)
        self.assertNotIn("low.json", content)
        self.assertIn("architectural_shift", content)
        self.assertIn("Moved to Go", content)

if __name__ == "__main__":
    unittest.main()
