#!/usr/bin/env python3
import unittest
import sys
import os
import tempfile
import shutil
from pathlib import Path

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev", "misc"]:
        sys.path.append(str(REPO_ROOT / ".agent" / "scripts" / domain))

import orchestration.dead_ends as de


class TestDeadEnds(unittest.TestCase):
    def setUp(self):
        # Redirect registry path to a temp file
        self.temp_dir = tempfile.mkdtemp()
        self.orig_registry_path = de.REGISTRY_PATH
        de.REGISTRY_PATH = Path(self.temp_dir) / "dead_ends.json"

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        de.REGISTRY_PATH = self.orig_registry_path

    def test_normalize_code(self):
        code1 = "func foo() {\n\t// comment here\n\treturn nil\n}"
        code2 = "func foo() { return nil }"
        self.assertEqual(de.normalize_code(code1), de.normalize_code(code2))

        code_with_comments = """
        /* Multi-line
           comment */
        x = 10 # inline comment
        """
        code_clean = "x=10"
        self.assertEqual(de.normalize_code(code_with_comments), de.normalize_code(code_clean))

    def test_log_and_check_dead_end(self):
        file_path = "main.go"
        patch = "x := 10\nfmt.Println(x)"
        error = "x declared but not used"
        
        self.assertFalse(de.is_dead_end(file_path, patch))
        de.log_dead_end(file_path, patch, error)
        self.assertTrue(de.is_dead_end(file_path, patch))

    def test_fuzzy_matching(self):
        file_path = "main.go"
        patch_original = "x := 10 // first attempt"
        patch_fuzzy = "x:=10 /* second attempt */"
        
        de.log_dead_end(file_path, patch_original, "some error")
        self.assertTrue(de.is_dead_end(file_path, patch_fuzzy))

    def test_clear_dead_ends(self):
        file_path = "main.go"
        patch = "x := 10"
        de.log_dead_end(file_path, patch, "error")
        self.assertTrue(de.is_dead_end(file_path, patch))
        
        de.clear_dead_ends()
        self.assertFalse(de.is_dead_end(file_path, patch))


if __name__ == "__main__":
    unittest.main()
