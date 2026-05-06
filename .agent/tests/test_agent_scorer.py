#!/usr/bin/env python3
import unittest
import json
import os
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile

# Antigravity Standard: Path Resolution
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))

import agent_scorer

class TestAgentScorer(unittest.TestCase):
    def setUp(self):
        # Create a temporary file for testing
        self.test_file = NamedTemporaryFile(delete=False, suffix=".jsonl")
        self.test_file.close()
        self.original_data_file = agent_scorer.DATA_FILE
        agent_scorer.DATA_FILE = Path(self.test_file.name)

    def tearDown(self):
        # Clean up
        if os.path.exists(self.test_file.name):
            os.remove(self.test_file.name)
        agent_scorer.DATA_FILE = self.original_data_file

    def test_log_score(self):
        agent_scorer.log_score("test-agent", "TASK-1", 5.0, "Excellent work")
        
        # Verify file content
        with open(self.test_file.name, "r") as f:
            lines = f.readlines()
            self.assertEqual(len(lines), 1)
            data = json.loads(lines[0])
            self.assertEqual(data["agent"], "test-agent")
            self.assertEqual(data["score"], 5.0)

    def test_get_stats(self):
        # Log multiple scores
        agent_scorer.log_score("agent-a", "T1", 5.0)
        agent_scorer.log_score("agent-a", "T2", 3.0)
        agent_scorer.log_score("agent-b", "T3", 4.0)
        
        stats = agent_scorer.get_stats()
        self.assertEqual(stats["agent-a"]["avg"], 4.0)
        self.assertEqual(stats["agent-a"]["count"], 2)
        self.assertEqual(stats["agent-b"]["avg"], 4.0)
        self.assertEqual(stats["agent-b"]["count"], 1)

    def test_get_stats_filtered(self):
        agent_scorer.log_score("agent-a", "T1", 5.0)
        agent_scorer.log_score("agent-b", "T3", 4.0)
        
        stats = agent_scorer.get_stats("agent-a")
        self.assertIn("agent-a", stats)
        self.assertNotIn("agent-b", stats)

if __name__ == "__main__":
    unittest.main()
