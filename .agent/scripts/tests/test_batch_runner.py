#!/usr/bin/env python3
import unittest
import json
import sys
import os
import shutil
from pathlib import Path
from io import StringIO
from unittest.mock import patch, MagicMock

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev", "misc"]:
        sys.path.append(str(REPO_ROOT / ".agent" / "scripts" / domain))

import orchestration.batch_runner as batch_runner

class TestBatchRunner(unittest.TestCase):
    def setUp(self):
        self.test_root = REPO_ROOT / "scratch" / "test_batch_runner"
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.agents_dir = self.test_root / "agents"
        self.agents_dir.mkdir()
        (self.agents_dir / "agent-1.md").write_text("info")
        (self.agents_dir / "agent-2.md").write_text("info")
        
        self.bus_file = self.test_root / "bus" / "context.json"
        self.bus_file.parent.mkdir()
        
        # Patching module variables
        self.p1 = patch('orchestration.batch_runner.AGENTS_DIR', self.agents_dir)
        self.p2 = patch('orchestration.batch_runner.BUS_FILE', self.bus_file)
        self.p1.start()
        self.p2.start()

    def tearDown(self):
        self.p1.stop()
        self.p2.stop()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_get_available_agents(self):
        agents = batch_runner.get_available_agents()
        self.assertCountEqual(agents, {"agent-1", "agent-2"})

    def test_validate_batch_valid(self):
        batch = {
            "tasks": [
                {"agent": "agent-1", "instruction": "do stuff"},
                {"agent": "agent-2", "instruction": "more stuff"}
            ]
        }
        errors = batch_runner.validate_batch(batch)
        self.assertEqual(len(errors), 0)

    def test_validate_batch_invalid(self):
        batch = {
            "tasks": [
                {"agent": "unknown", "instruction": "do stuff"},
                {"missing_agent": "oops"}
            ]
        }
        errors = batch_runner.validate_batch(batch)
        self.assertTrue(any("unknown agent 'unknown'" in e for e in errors))
        self.assertTrue(any("missing 'agent' field" in e for e in errors))

    def test_generate_batch(self):
        with patch('sys.stdout', new=StringIO()) as fake_out:
            batch_runner.generate_batch("agent-1, agent-2", "Test Task")
            output = json.loads(fake_out.getvalue().strip())
            self.assertEqual(len(output["tasks"]), 2)
            self.assertEqual(output["tasks"][0]["agent"], "agent-1")
            self.assertEqual(output["tasks"][1]["agent"], "agent-2")

if __name__ == "__main__":
    unittest.main()
