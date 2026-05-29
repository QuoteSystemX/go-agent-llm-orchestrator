#!/usr/bin/env python3
import unittest
import shutil
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

import context.semantic_context_optimizer as optimizer

class TestSemanticContextOptimizer(unittest.TestCase):
    def test_optimize_context_short(self):
        text = "Header\n------------------------------\nResult 1"
        res = optimizer.optimize_context(text, max_length=2000)
        self.assertEqual(res, text)

    def test_optimize_context_long(self):
        sections = ["Header"]
        for i in range(1, 10):
            sections.append(f"Result {i} " * 10)
        text = "\n------------------------------\n".join(sections)
        
        with patch('sys.stdout', new=MagicMock()):
            res = optimizer.optimize_context(text, max_length=150)
            
        # It should keep header and maybe Result 1, then truncate
        self.assertLessEqual(len(res), max_length:=150 + 50) # Approx length check
        self.assertIn("Header", res)
        # Should not have all 9 results
        self.assertNotIn("Result 9", res)

    def test_main_direct_call(self):
        """Call optimize_context directly (same logic as __main__ block)."""
        text = "Header\n------------------------------\nResult 1"
        res = optimizer.optimize_context(text, max_length=2000)
        self.assertEqual(res, text)
        self.assertIn("Header", res)

if __name__ == "__main__":
    unittest.main()
