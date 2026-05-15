#!/usr/bin/env python3
import unittest
import json
import sys
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

import orchestration.wave_dispatcher as wave_dispatcher

class TestWaveDispatcher(unittest.TestCase):
    def test_parse_mermaid_dag(self):
        content = "graph TD\n  A[Start] --> B[Middle]\n  B --> C[End]"
        nodes, edges = wave_dispatcher.parse_mermaid_dag(content)
        self.assertIn("A", nodes)
        self.assertIn("B", nodes)
        self.assertIn("C", nodes)
        self.assertEqual(len(edges), 2)
        self.assertIn(("A", "B"), edges)
        self.assertIn(("B", "C"), edges)

    def test_get_execution_waves(self):
        nodes = {"A": [], "B": [], "C": [], "D": []}
        edges = [("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")]
        waves = wave_dispatcher.get_execution_waves(nodes, edges)
        
        self.assertEqual(len(waves), 3)
        self.assertEqual(waves[0], ["A"])
        self.assertCountEqual(waves[1], ["B", "C"])
        self.assertEqual(waves[2], ["D"])

    def test_check_ready_nodes(self):
        nodes = ["A", "B", "C"]
        edges = [("A", "B"), ("A", "C")]
        
        # Case 1: A is completed, B and C should be ready
        session_state = {"task_A": "completed", "task_B": "pending", "task_C": "pending"}
        ready = wave_dispatcher.check_ready_nodes(nodes, edges, session_state)
        self.assertCountEqual(ready, ["B", "C"])
        
        # Case 2: Nothing completed
        session_state = {"task_A": "pending", "task_B": "pending"}
        ready = wave_dispatcher.check_ready_nodes(nodes, edges, session_state)
        self.assertEqual(ready, ["A"])

    @patch('orchestration.wave_dispatcher.subprocess.run')
    def test_execute_node(self, mock_run):
        mock_run.return_value = MagicMock(stdout="sub_sid_123\n")
        
        # Test normal execution
        wave_dispatcher.execute_node("sid", "A", "Just a task")
        self.assertEqual(mock_run.call_count, 1) # Only set-state
        
        # Test recursive execution
        mock_run.reset_mock()
        wave_dispatcher.execute_node("sid", "B", "[RECURSIVE] Spawning...")
        # Should call: 1. init (sub-sid), 2. set-state (subsession_B), 3. set-state (task_B)
        self.assertEqual(mock_run.call_count, 3)

if __name__ == "__main__":
    unittest.main()
