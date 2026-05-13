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

import health.security_scan as security_scan

class TestSecurityScan(unittest.TestCase):
    def setUp(self):
        self.test_root = REPO_ROOT / "scratch" / "test_security"
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        # Patch REPO_ROOT in module
        self.patcher = patch('health.security_scan.REPO_ROOT', self.test_root)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_scan_file_secrets(self):
        # Create a file with a secret
        secret_file = self.test_root / "secret.py"
        secret_file.write_text('API_KEY = "ghp_123456789012345678901234567890123456"')
        
        findings = security_scan.scan_file(secret_file)
        self.assertTrue(any(f["type"] == "SECRET" for f in findings))
        self.assertTrue(any("GitHub personal access token" in f["description"] for f in findings))

    def test_scan_file_dangerous_patterns(self):
        # Create a file with dangerous python code
        danger_file = self.test_root / "danger.py"
        danger_file.write_text('eval("import os; os.system(\'rm -rf /\')")')
        
        findings = security_scan.scan_file(danger_file)
        # Should have 2 findings: eval and os.system
        self.assertEqual(len(findings), 2)
        self.assertTrue(any("Use of eval()" in f["description"] for f in findings))

    def test_should_skip(self):
        self.assertTrue(security_scan.should_skip(Path(".git/config")))
        self.assertTrue(security_scan.should_skip(Path("node_modules/package.json")))
        self.assertTrue(security_scan.should_skip(Path("security_scan.py")))
        self.assertFalse(security_scan.should_skip(Path("src/main.py")))

    def test_check_forbidden_files(self):
        # Create forbidden files
        (self.test_root / "test.bak").touch()
        (self.test_root / "error.log").touch()
        (self.test_root / "normal.py").touch()
        
        findings = security_scan.check_forbidden_files()
        self.assertTrue(any("test.bak" in f["file"] for f in findings))
        self.assertTrue(any("error.log" in f["file"] for f in findings))
        self.assertFalse(any("normal.py" in f["file"] for f in findings))

if __name__ == "__main__":
    unittest.main()
