#!/usr/bin/env python3
import unittest
import shutil
import json
import sys
import os
from pathlib import Path

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev", "misc"]:
        sys.path.append(str(REPO_ROOT / ".agent" / "scripts" / domain))

import orchestration.session_manager as session_manager

class TestSessionManager(unittest.TestCase):
    def setUp(self):
        self.test_root = REPO_ROOT / "scratch" / "test_session_mgr"
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)

    def tearDown(self):
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_analyze_go_mod(self):
        # Create a Go project structure
        go_mod = self.test_root / "go.mod"
        go_mod.write_text("module github.com/test/project\ngo 1.21\nrequire github.com/gin-gonic/gin v1.9.0")
        
        # Must have go sources to be detected as Go
        (self.test_root / "main.go").write_text("package main")
        
        info = session_manager.analyze_go_mod(self.test_root)
        self.assertEqual(info["type"], "Go")
        self.assertEqual(info["module"], "github.com/test/project")
        self.assertIn("Gin", info["stack"])

    def test_analyze_package_json(self):
        pkg_json = self.test_root / "package.json"
        pkg_json.write_text(json.dumps({
            "name": "node-test",
            "dependencies": {"next": "13.0.0", "tailwindcss": "3.0.0"},
            "scripts": {"dev": "next dev"}
        }))
        
        info = session_manager.analyze_package_json(self.test_root)
        self.assertEqual(info["type"], "Node.js")
        self.assertIn("Next.js", info["stack"])
        self.assertIn("dev", info["scripts"])

    def test_analyze_python_project(self):
        reqs = self.test_root / "requirements.txt"
        reqs.write_text("fastapi\npytest\n")
        
        info = session_manager.analyze_python_project(self.test_root)
        self.assertEqual(info["type"], "Python")
        self.assertIn("FastAPI", info["stack"])
        self.assertIn("Pytest", info["stack"])

    def test_analyze_rust_project(self):
        cargo = self.test_root / "Cargo.toml"
        cargo.write_text("[package]\nname = \"rust-test\"\n[dependencies]\ntokio = \"1.0\"")
        
        info = session_manager.analyze_rust_project(self.test_root)
        self.assertEqual(info["type"], "Rust")
        self.assertIn("Tokio", info["stack"])

    def test_count_files(self):
        (self.test_root / "test.go").write_text("")
        (self.test_root / "test.py").write_text("")
        (self.test_root / "test.ts").write_text("")
        (self.test_root / "README.md").write_text("")
        
        # Test exclude
        node_modules = self.test_root / "node_modules"
        node_modules.mkdir()
        (node_modules / "junk.js").write_text("")
        
        stats = session_manager.count_files(self.test_root)
        self.assertEqual(stats["go"], 1)
        self.assertEqual(stats["py"], 1)
        self.assertEqual(stats["ts"], 1)
        self.assertEqual(stats["other"], 1) # README.md
        self.assertEqual(stats["total"], 4) # Should NOT count node_modules

if __name__ == "__main__":
    unittest.main()
