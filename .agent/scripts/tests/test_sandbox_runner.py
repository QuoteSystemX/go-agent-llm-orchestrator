#!/usr/bin/env python3
import unittest
import unittest.mock
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

import dev.sandbox_runner as sandbox

class TestSandboxRunner(unittest.TestCase):
    def test_analyze_code_dangerous_imports(self):
        code = "import os\nos.remove('file')"
        safe, msg = sandbox.analyze_code(code)
        self.assertFalse(safe)
        self.assertIn("Dangerous import detected: os", msg)

        code = "from subprocess import run"
        safe, msg = sandbox.analyze_code(code)
        self.assertFalse(safe)
        self.assertIn("Dangerous import detected: subprocess", msg)

    def test_analyze_code_dangerous_calls(self):
        code = "eval('1+1')"
        safe, msg = sandbox.analyze_code(code)
        self.assertFalse(safe)
        self.assertIn("Dangerous function call detected: eval", msg)

        code = "exec('x=1')"
        safe, msg = sandbox.analyze_code(code)
        self.assertFalse(safe)
        self.assertIn("Dangerous function call detected: exec", msg)

    def test_analyze_code_safe(self):
        code = "print('hello world')\nx = [i for i in range(10)]"
        safe, msg = sandbox.analyze_code(code)
        self.assertTrue(safe)

    def test_run_in_sandbox_success(self):
        code = "print('SANDBOX_TEST_OK')"
        success = sandbox.run_in_sandbox(code)
        self.assertTrue(success)

    def test_run_in_sandbox_veto(self):
        code = "import socket"
        success = sandbox.run_in_sandbox(code)
        self.assertFalse(success)

    def test_run_in_sandbox_timeout(self):
        code = "import time\nwhile True: pass"
        # We need to mock time.sleep or similar if we want it to be fast, 
        # but sandbox uses subprocess.run with timeout=5.
        # I'll use a shorter timeout in the script if I could, 
        # but for unit test I'll just skip or use a very short infinite loop.
        # Actually, let's just test that it DOES timeout.
        with unittest.mock.patch('subprocess.run', side_effect=sandbox.subprocess.TimeoutExpired(['cmd'], 5)):
            success = sandbox.run_in_sandbox("print('safe but mocked timeout')")
            self.assertFalse(success)

if __name__ == "__main__":
    unittest.main()
