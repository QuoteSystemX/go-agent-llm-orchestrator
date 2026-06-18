#!/usr/bin/env python3
"""Tests for chaos/sandbox_runner.py — resource limit enforcement.

Validates that _apply_limits():
  - Raises RuntimeError on critical limit (AS/CPU) failures
  - Returns warnings on optional limit (STACK/FSIZE) failures
  - Verifies critical limits via getrlimit() after setting

And that run_sandboxed() propagates warnings into its JSON response.
"""

import unittest
import unittest.mock
import sys
import os
from pathlib import Path

# ── Repo-aware import ──
try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))
    for domain in ["health", "context", "delivery", "orchestration", "analysis",
                    "models", "knowledge", "dev", "misc", "chaos"]:
        sys.path.append(str(REPO_ROOT / ".agent" / "scripts" / domain))

import chaos.sandbox_runner as sandbox


class TestApplyLimits(unittest.TestCase):
    """Tests for the refactored _apply_limits() function."""

    def setUp(self):
        # Save original MAX_* values to restore later
        self._orig_ram = sandbox.MAX_RAM
        self._orig_cpu = sandbox.MAX_CPU
        self._orig_stack = sandbox.MAX_STACK
        self._orig_fsize = sandbox.MAX_FSIZE

    def tearDown(self):
        # Restore original values
        sandbox.MAX_RAM = self._orig_ram
        sandbox.MAX_CPU = self._orig_cpu
        sandbox.MAX_STACK = self._orig_stack
        sandbox.MAX_FSIZE = self._orig_fsize

    @unittest.mock.patch("chaos.sandbox_runner.resource.setrlimit")
    @unittest.mock.patch("chaos.sandbox_runner.resource.getrlimit")
    def test_apply_limits_success_returns_empty_list(self, mock_get, mock_set):
        """All limits succeed → returns empty warnings list."""
        def getrlimit_side(rlimit):
            if rlimit == sandbox.resource.RLIMIT_AS:
                return (sandbox.MAX_RAM, sandbox.MAX_RAM)
            if rlimit == sandbox.resource.RLIMIT_CPU:
                return (sandbox.MAX_CPU, sandbox.MAX_CPU + 1)
            return (sandbox.MAX_STACK, sandbox.MAX_STACK)

        mock_get.side_effect = getrlimit_side
        warnings = sandbox._apply_limits()
        self.assertEqual(warnings, [])
        self.assertEqual(mock_set.call_count, 4)

    @unittest.mock.patch("chaos.sandbox_runner.resource.setrlimit")
    @unittest.mock.patch("chaos.sandbox_runner.resource.getrlimit")
    def test_critical_limit_failure_raises_runtime_error(self, mock_get, mock_set):
        """AS (RAM) critical limit failure → RuntimeError, not silent pass."""
        mock_set.side_effect = PermissionError("setrlimit failed: Operation not permitted")
        with self.assertRaises(RuntimeError) as ctx:
            sandbox._apply_limits()
        self.assertIn("CRITICAL", str(ctx.exception))
        self.assertIn("setrlimit failed", str(ctx.exception))

    @unittest.mock.patch("chaos.sandbox_runner.resource.setrlimit")
    @unittest.mock.patch("chaos.sandbox_runner.resource.getrlimit")
    def test_optional_limit_failure_returns_warning(self, mock_get, mock_set):
        """STACK optional limit fails → warning returned, no exception."""
        def getrlimit_side(rlimit):
            if rlimit == sandbox.resource.RLIMIT_AS:
                return (sandbox.MAX_RAM, sandbox.MAX_RAM)
            if rlimit == sandbox.resource.RLIMIT_CPU:
                return (sandbox.MAX_CPU, sandbox.MAX_CPU + 1)
            return (sandbox.MAX_STACK, sandbox.MAX_STACK)

        mock_get.side_effect = getrlimit_side

        def setrlimit_side_effect(rlimit, value):
            if rlimit == sandbox.resource.RLIMIT_STACK:
                raise PermissionError("RLIMIT_STACK not supported")
            return None

        mock_set.side_effect = setrlimit_side_effect
        warnings = sandbox._apply_limits()
        self.assertEqual(len(warnings), 1)
        self.assertIn("RLIMIT_STACK", warnings[0])

    @unittest.mock.patch("chaos.sandbox_runner.resource.setrlimit")
    @unittest.mock.patch("chaos.sandbox_runner.resource.getrlimit")
    def test_verification_failure_raises_runtime_error(self, mock_get, mock_set):
        """getrlimit returns different value than set → RuntimeError."""
        # Simulate getrlimit returning a lower limit than what we requested
        def getrlimit_side_effect(rlimit):
            if rlimit == sandbox.resource.RLIMIT_AS:
                return (sandbox.MAX_RAM // 2, sandbox.MAX_RAM)  # soft != expected
            return (sandbox.MAX_RAM, sandbox.MAX_RAM)

        mock_get.side_effect = getrlimit_side_effect
        with self.assertRaises(RuntimeError) as ctx:
            sandbox._apply_limits()
        self.assertIn("verification failed", str(ctx.exception))
        self.assertIn("RLIMIT_AS", str(ctx.exception))

    @unittest.mock.patch("chaos.sandbox_runner.resource.setrlimit")
    @unittest.mock.patch("chaos.sandbox_runner.resource.getrlimit")
    def test_verification_exception_falls_back_to_warning(self, mock_get, mock_set):
        """getrlimit itself raises → warning, not crash."""
        def getrlimit_side(rlimit):
            if rlimit == sandbox.resource.RLIMIT_AS:
                raise OSError("getrlimit not available")
            if rlimit == sandbox.resource.RLIMIT_CPU:
                return (sandbox.MAX_CPU, sandbox.MAX_CPU + 1)
            return (sandbox.MAX_STACK, sandbox.MAX_STACK)

        mock_get.side_effect = getrlimit_side
        warnings = sandbox._apply_limits()
        self.assertGreaterEqual(len(warnings), 1)
        self.assertTrue(any("RLIMIT_AS" in w for w in warnings))


class TestRunSandboxedWarnings(unittest.TestCase):
    """Tests that run_sandboxed() correctly propagates warnings."""

    @unittest.mock.patch("chaos.sandbox_runner._apply_limits")
    @unittest.mock.patch("chaos.sandbox_runner._execute")
    def test_run_sandboxed_includes_warnings_in_success(self, mock_exec, mock_limits):
        """When _apply_limits returns warnings, result dict includes them."""
        mock_limits.return_value = ["RLIMIT_STACK could not be applied: test"]
        mock_exec.return_value = "ok"

        result = sandbox.run_sandboxed({"target": "os.path.join", "payload": "/"})

        self.assertTrue(result["ok"])
        self.assertIn("warnings", result)
        self.assertEqual(len(result["warnings"]), 1)
        self.assertIn("RLIMIT_STACK", result["warnings"][0])

    @unittest.mock.patch("chaos.sandbox_runner._apply_limits")
    @unittest.mock.patch("chaos.sandbox_runner._execute")
    def test_run_sandboxed_no_warnings_key_when_empty(self, mock_exec, mock_limits):
        """When _apply_limits returns [], result dict has no 'warnings' key."""
        mock_limits.return_value = []
        mock_exec.return_value = "ok"

        result = sandbox.run_sandboxed({"target": "os.path.join", "payload": "/"})

        self.assertTrue(result["ok"])
        self.assertNotIn("warnings", result)

    @unittest.mock.patch("chaos.sandbox_runner._apply_limits")
    @unittest.mock.patch("chaos.sandbox_runner._execute")
    def test_run_sandboxed_includes_warnings_on_error(self, mock_exec, mock_limits):
        """When execution fails but there are warnings, warnings still propagate."""
        mock_limits.return_value = ["RLIMIT_FSIZE could not be applied: test"]
        mock_exec.side_effect = ValueError("fuzz payload rejected")

        result = sandbox.run_sandboxed({"target": "os.path.join", "payload": "/"})

        self.assertFalse(result["ok"])
        self.assertIn("warnings", result)
        self.assertIn("RLIMIT_FSIZE", result["warnings"][0])


if __name__ == "__main__":
    unittest.main()
