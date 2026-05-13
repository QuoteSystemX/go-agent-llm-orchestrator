#!/usr/bin/env python3
import unittest
import shutil
import sys
from pathlib import Path

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))

import test_factory

class TestTestFactory(unittest.TestCase):
    def setUp(self):
        self.test_root = REPO_ROOT / "scratch" / "test_factory"
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)

    def tearDown(self):
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_generate_python_test(self):
        target = self.test_root / "logic.py"
        target.write_text("print('hi')")
        
        result = test_factory.generate_test(str(target))
        self.assertIn("✅ Test file created", result)
        
        test_file = self.test_root / "tests" / "test_logic.py"
        self.assertTrue(test_file.exists())
        self.assertIn("import unittest", test_file.read_text())

    def test_generate_go_test(self):
        target = self.test_root / "logic.go"
        target.write_text("package main")
        
        result = test_factory.generate_test(str(target))
        self.assertIn("✅ Test file created", result)
        
        test_file = self.test_root / "logic_test.go"
        self.assertTrue(test_file.exists())
        self.assertIn("func TestLogic", test_file.read_text())

    def test_generate_missing(self):
        result = test_factory.generate_test("non_existent.py")
        self.assertIn("❌ Target", result)

if __name__ == "__main__":
    unittest.main()
