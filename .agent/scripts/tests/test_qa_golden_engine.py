#!/usr/bin/env python3
import unittest
import sys
import os
import shutil
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

import dev.qa_golden_engine as qa

class TestQAGoldenEngine(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_qa_golden").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.data_path = self.test_root / ".agent" / "data" / "golden_set.json"
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)

    def tearDown(self):
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_engine_init_and_save(self):
        engine = qa.GoldenSetEngine(data_path=str(self.data_path))
        self.assertEqual(len(engine.golden_set), 0)
        
        engine.add_golden_pair("my query", ["pattern1", "pattern2"])
        self.assertTrue(self.data_path.exists())
        
        # Load fresh
        engine2 = qa.GoldenSetEngine(data_path=str(self.data_path))
        self.assertEqual(len(engine2.golden_set), 1)
        self.assertEqual(engine2.golden_set[0]["query"], "my query")

    def test_validate_output(self):
        engine = qa.GoldenSetEngine(data_path=str(self.data_path))
        engine.add_golden_pair("auth implementation", ["JWT", "bcrypt"])
        
        # Missing patterns
        result_fail = engine.validate_output("how to do auth implementation", "Use simple hashing")
        self.assertEqual(result_fail["status"], "FAIL")
        self.assertIn("JWT", result_fail["missing_patterns"])
        
        # Passing patterns
        result_pass = engine.validate_output("auth implementation", "Use JWT and bcrypt")
        self.assertEqual(result_pass["status"], "PASS")
        self.assertEqual(len(result_pass["missing_patterns"]), 0)
        
        # No match
        result_skip = engine.validate_output("database stuff", "SQL")
        self.assertEqual(result_skip["status"], "SKIPPED")

if __name__ == "__main__":
    unittest.main()
