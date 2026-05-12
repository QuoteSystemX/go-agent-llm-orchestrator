#!/usr/bin/env python3
import unittest
import os
import shutil
from pathlib import Path
import sys

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev", "misc"]:
        sys.path.append(str(REPO_ROOT / ".agent" / "scripts" / domain))

import health.alignment_oracle; import sys; sys.modules['alignment_oracle'] = sys.modules['health.alignment_oracle']; import health.alignment_oracle as alignment_oracle

class TestAlignmentOracle(unittest.TestCase):
    def setUp(self):
        self.test_root = REPO_ROOT / "scratch" / "test_oracle"
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)

    def tearDown(self):
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_check_dna_alignment(self):
        # Case 1: Excessive comments
        bad_content = "# Comment\n" * 10 + "print('hello')"
        warnings = alignment_oracle.check_dna_alignment(bad_content)
        self.assertTrue(any("DNA MISALIGNMENT" in w for w in warnings))
        
        # Case 2: Silent failure
        silent_fail = "try:\n    do_something()\nexcept:\n    pass"
        warnings = alignment_oracle.check_dna_alignment(silent_fail)
        self.assertTrue(any("SILENT FAILURE" in w for w in warnings))

    def test_check_complexity_fallback(self):
        # Create a large file
        large_file = self.test_root / "large.py"
        large_file.write_text("print('hello')\n" * 400)
        
        warnings = alignment_oracle.check_complexity(large_file)
        self.assertTrue(any("FILE LENGTH" in w for w in warnings))

if __name__ == "__main__":
    unittest.main()
