#!/usr/bin/env python3
import unittest
import sys
from unittest.mock import patch, MagicMock

# Antigravity Domain-Aware Import Logic
import os
from pathlib import Path

try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev", "misc"]:
        sys.path.append(str(REPO_ROOT / ".agent" / "scripts" / domain))

import analysis.resource_optimizer as optimizer

class TestResourceOptimizer(unittest.TestCase):
    @patch('sys.stdout', new_callable=MagicMock)
    def test_run_optimization_audit(self, mock_stdout):
        # We just verify it executes without error and prints something
        optimizer.run_optimization_audit()
        
        # Verify it writes output
        mock_stdout.write.assert_called()
        
        # We can extract all printed lines by iterating the mock calls
        output = "".join([call.args[0] for call in mock_stdout.write.call_args_list])
        self.assertIn("Optimization Suggestions", output)
        self.assertIn("[OPTIMIZATION AUDIT COMPLETE]", output)

if __name__ == "__main__":
    unittest.main()
