#!/usr/bin/env python3
import unittest
import sys
import shutil
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

import dev.visualize_deps as visualizer

class TestVisualizeDeps(unittest.TestCase):
    def setUp(self):
        self.test_root = REPO_ROOT / "scratch" / "test_visualize"
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.patch_repo = patch('dev.visualize_deps.REPO_ROOT', self.test_root)
        self.patch_repo.start()

    def tearDown(self):
        self.patch_repo.stop()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_scan_python_imports(self):
        py_file = self.test_root / "script.py"
        py_file.write_text("import os\nimport custom_lib\nfrom other import thing\n# import ignored")
        
        imports = visualizer.scan_python_imports(py_file)
        self.assertIn("custom_lib", imports)
        self.assertIn("other", imports)
        self.assertNotIn("os", imports)
        self.assertNotIn("ignored", imports)

    def test_scan_go_imports(self):
        go_file = self.test_root / "main.go"
        go_content = """
package main
import (
    "fmt"
    "github.com/QuoteSystemX/prompt-library/internal/storage"
    "github.com/external/pkg"
)
func main() {}
"""
        go_file.write_text(go_content)
        
        imports = visualizer.scan_go_imports(go_file)
        self.assertIn("internal", imports)
        self.assertIn("pkg", imports)
        self.assertNotIn("fmt", imports)

    def test_generate_mermaid(self):
        # Create a mock setup
        scripts_dir = self.test_root / ".agent" / "scripts"
        scripts_dir.mkdir(parents=True)
        (scripts_dir / "agent.py").write_text("import utils")
        
        res = visualizer.generate_mermaid()
        self.assertIn("graph TD", res)
        self.assertIn("agent --> utils", res)

if __name__ == "__main__":
    unittest.main()
