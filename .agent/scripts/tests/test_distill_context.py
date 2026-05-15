#!/usr/bin/env python3
import unittest
import shutil
import sys
import json
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

import context.distill_context as distiller

class TestDistillContext(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_distill").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.bus_dir = self.test_root / ".agent" / "bus"
        self.bus_dir.mkdir(parents=True)
        self.bus_file = self.bus_dir / "context.json"
        self.snapshot_dir = self.bus_dir / "snapshots"
        self.snapshot_dir.mkdir(parents=True)
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)
        
        # Patch paths
        self.patch_root = patch('context.distill_context.REPO_ROOT', self.test_root)
        self.patch_bus = patch('context.distill_context.BUS_FILE', self.bus_file)
        self.patch_snapshot = patch('context.distill_context.SNAPSHOT_DIR', self.snapshot_dir)
        self.patch_root.start()
        self.patch_bus.start()
        self.patch_snapshot.start()

    def tearDown(self):
        self.patch_root.stop()
        self.patch_bus.stop()
        self.patch_snapshot.stop()
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_distill_from_bus_logic(self):
        bus_data = {
            "objects": [
                {
                    "id": "v1", "type": "verification_result", "author": "tester",
                    "content": {"status": "PASS", "summary": "Code is good"}
                },
                {
                    "id": "r1", "type": "requirement", "author": "user",
                    "content": {"tasks": [{"agent": "a1", "instruction": "Do thing"}]}
                }
            ]
        }
        self.bus_file.write_text(json.dumps(bus_data))
        
        snapshot = distiller.distill_from_bus()
        content = snapshot["content"]
        self.assertIn("[PASS] Code is good", content["decisions"])
        self.assertIn("a1: Do thing", content["pending_tasks"])
        self.assertIn("tester", content["summary"])

    def test_save_snapshot(self):
        snapshot = distiller._create_snapshot("Summary", ["D1"], ["P1"], {"f1": "a1"})
        archive_path = distiller.save_snapshot(snapshot)
        
        self.assertTrue(archive_path.exists())
        self.assertTrue(self.bus_file.exists())
        
        bus_data = json.loads(self.bus_file.read_text())
        self.assertEqual(bus_data["objects"][-1]["id"], snapshot["id"])

    def test_empty_bus(self):
        self.bus_file.write_text(json.dumps({"objects": []}))
        snapshot = distiller.distill_from_bus()
        self.assertEqual(snapshot["content"]["summary"], "No data on bus.")

if __name__ == "__main__":
    unittest.main()
