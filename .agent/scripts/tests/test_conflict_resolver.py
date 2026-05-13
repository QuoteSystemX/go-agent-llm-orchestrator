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

import context.conflict_resolver as resolver

class TestConflictResolver(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_conflict_resolver").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.bus_dir = self.test_root / ".agent" / "bus"
        self.bus_dir.mkdir(parents=True)
        self.bus_file = self.bus_dir / "context.json"
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)
        
        # Patch paths
        self.patch_bus_dir = patch('context.conflict_resolver.BUS_DIR', self.bus_dir)
        self.patch_bus_dir.start()

    def tearDown(self):
        self.patch_bus_dir.stop()
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_no_conflicts(self):
        data = {
            "objects": [
                {"id": "obj1", "content": {"v": 1}, "author": "a1", "timestamp": "2026-01-01T00:00:00Z"}
            ]
        }
        self.bus_file.write_text(json.dumps(data))
        
        result = resolver.resolve_conflicts()
        self.assertIn("No conflicts detected", result)

    def test_detect_conflict(self):
        data = {
            "objects": [
                {"id": "obj1", "content": {"v": 1}, "author": "a1", "timestamp": "2026-01-01T00:00:00Z"},
                {"id": "obj1", "content": {"v": 2}, "author": "a2", "timestamp": "2026-01-01T00:00:01Z"}
            ]
        }
        self.bus_file.write_text(json.dumps(data))
        
        result = resolver.resolve_conflicts()
        self.assertIn("BUS CONFLICTS DETECTED", result)
        self.assertIn("ID: 'obj1'", result)

    def test_fix_conflict(self):
        data = {
            "objects": [
                {"id": "obj1", "content": {"v": 1}, "author": "a1", "timestamp": "2026-01-01T00:00:00Z"},
                {"id": "obj1", "content": {"v": 2}, "author": "a2", "timestamp": "2026-01-01T00:00:01Z"}
            ]
        }
        self.bus_file.write_text(json.dumps(data))
        
        result = resolver.resolve_conflicts(fix=True)
        self.assertIn("Fixed 1 conflicts", result)
        
        # Verify only latest remains
        fixed_data = json.loads(self.bus_file.read_text())
        self.assertEqual(len(fixed_data["objects"]), 1)
        self.assertEqual(fixed_data["objects"][0]["content"]["v"], 2)

    def test_duplicate_same_content(self):
        # Should NOT count as a conflict if content is identical
        data = {
            "objects": [
                {"id": "obj1", "content": {"v": 1}, "author": "a1", "timestamp": "2026-01-01T00:00:00Z"},
                {"id": "obj1", "content": {"v": 1}, "author": "a1", "timestamp": "2026-01-01T00:00:00Z"}
            ]
        }
        self.bus_file.write_text(json.dumps(data))
        
        result = resolver.resolve_conflicts()
        self.assertIn("No conflicts detected", result)

if __name__ == "__main__":
    unittest.main()
