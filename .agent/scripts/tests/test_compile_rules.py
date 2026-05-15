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

import dev.compile_rules as compiler

class TestCompileRules(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_compiler").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.rules_dir = self.test_root / ".agent" / "rules" / "gemini"
        self.rules_dir.mkdir(parents=True)
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)

    def tearDown(self):
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_compile_gemini_rules_basic(self):
        (self.rules_dir / "01_rule.md").write_text("# Rule 1")
        (self.rules_dir / "02_rule.md").write_text("# Rule 2")
        
        compiler.compile_gemini_rules()
        
        output_file = self.test_root / ".agent" / "rules" / "GEMINI.md"
        self.assertTrue(output_file.exists())
        content = output_file.read_text()
        self.assertIn("# Rule 1", content)
        self.assertIn("# Rule 2", content)
        # Verify order
        self.assertTrue(content.find("# Rule 1") < content.find("# Rule 2"))

    def test_compile_gemini_rules_with_frontmatter(self):
        (self.rules_dir / "01_meta.md").write_text("---\nscope: global\n---\nBody")
        
        compiler.compile_gemini_rules()
        
        output_file = self.test_root / ".agent" / "rules" / "GEMINI.md"
        content = output_file.read_text()
        self.assertIn("> [!NOTE]", content)
        self.assertIn("> **scope: global**", content)
        self.assertIn("Body", content)

if __name__ == "__main__":
    unittest.main()
