#!/usr/bin/env python3
import unittest
import shutil
import sys
import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev", "misc"]:
        sys.path.append(str(REPO_ROOT / ".agent" / "scripts" / domain))

import context.context_pruner as pruner

class TestContextPruner(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_pruner").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.bus_dir = self.test_root / ".agent" / "bus"
        self.bus_dir.mkdir(parents=True)
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)
        
        # Patch BUS_PATH in pruner
        self.patch_bus = patch('context.context_pruner.BUS_PATH', self.bus_dir)
        self.patch_bus.start()

    def tearDown(self):
        self.patch_bus.stop()
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_prune_by_age(self):
        old_date = (datetime.now() - timedelta(days=10)).isoformat()
        
        # 1. Old and low priority -> Prune
        p1 = self.bus_dir / "old_low.json"
        p1.write_text(json.dumps({"created_at": old_date, "priority": 1}))
        
        # 2. Old but high priority -> Keep
        p2 = self.bus_dir / "old_high.json"
        p2.write_text(json.dumps({"created_at": old_date, "priority": 10}))
        
        # 3. New and low priority -> Keep
        p3 = self.bus_dir / "new_low.json"
        p3.write_text(json.dumps({"created_at": datetime.now().isoformat(), "priority": 1}))
        
        res = pruner.prune_bus()
        self.assertEqual(res["pruned"], 1)
        self.assertFalse(p1.exists())
        self.assertTrue(p2.exists())
        self.assertTrue(p3.exists())

    def test_summarize_logs(self):
        # Create a large log stream
        large_logs = ["Log line"] * 200
        p_logs = self.bus_dir / "large_logs.json"
        p_logs.write_text(json.dumps({
            "type": "log_stream",
            "payload": large_logs
        }))
        
        # Mock file size check (stat().st_size)
        with patch('pathlib.Path.stat') as mock_stat:
            mock_stat.return_value.st_size = 60000
            res = pruner.prune_bus()
            
        self.assertEqual(res["summarized"], 1)
        data = json.loads(p_logs.read_text())
        self.assertTrue(data["is_pruned"])
        self.assertEqual(len(data["payload"]), 41) # 20 + 1 + 20

if __name__ == "__main__":
    unittest.main()
