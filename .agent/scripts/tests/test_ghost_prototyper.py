#!/usr/bin/env python3
import unittest
import sys
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

import analysis.ghost_prototyper as ghost

class TestGhostPrototyper(unittest.TestCase):
    @patch('sys.stdout', new_callable=MagicMock)
    def test_run_ghost_proto_success(self, mock_stdout):
        ghost.run_ghost_proto("Build a simple server")
        output = "".join(call[0][0] for call in mock_stdout.write.call_args_list)
        self.assertIn("feasible", output)

    @patch('sys.stdout', new_callable=MagicMock)
    def test_run_ghost_proto_failure(self, mock_stdout):
        with self.assertRaises(SystemExit) as cm:
            ghost.run_ghost_proto("This is impossible to build")
        self.assertEqual(cm.exception.code, 1)
        output = "".join(call[0][0] for call in mock_stdout.write.call_args_list)
        self.assertIn("FAILED", output)

if __name__ == "__main__":
    unittest.main()
