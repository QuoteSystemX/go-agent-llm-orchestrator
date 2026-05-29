#!/usr/bin/env python3
import unittest
import json
import sys
from pathlib import Path
from io import StringIO
from unittest.mock import patch

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev", "misc"]:
        sys.path.append(str(REPO_ROOT / ".agent" / "scripts" / domain))

import orchestration.agent_arena as agent_arena

class TestAgentArena(unittest.TestCase):
    def test_conduct_debate(self):
        session_id = "test_session"
        role = "developer"
        candidates = ["agent-1", "agent-2"]
        subtask = "fix memory leak"
        
        report = agent_arena.conduct_debate(session_id, role, candidates, subtask)
        
        self.assertEqual(report["session_id"], session_id)
        self.assertEqual(report["role"], role)
        self.assertEqual(report["subtask"], subtask)
        self.assertEqual(len(report["candidates"]), 2)
        self.assertEqual(report["judge"], "project-planner")
        self.assertEqual(len(report["rounds"]), 2)

    def test_format_verdict(self):
        winner = "agent-1"
        risks = ["Slow implementation", "Potential drift"]
        
        verdict = agent_arena.format_verdict(winner, risks)
        
        self.assertEqual(verdict["winner"], winner)
        self.assertEqual(len(verdict["mitigation_plan"]), 2)
        self.assertIn("Address risk: Slow implementation", verdict["mitigation_plan"][0])
        self.assertEqual(verdict["status"], "decided_via_arena")

    def test_cli_execution(self):
        # Call the underlying functions directly since __main__ is not importable
        report = agent_arena.conduct_debate('sid', 'role', ['c1', 'c2'], 'subtask')
        self.assertIn('session_id', report)
        self.assertEqual(report['session_id'], 'sid')
        self.assertEqual(report['role'], 'role')
        self.assertIn('c1', report['candidates'])

if __name__ == "__main__":
    unittest.main()
