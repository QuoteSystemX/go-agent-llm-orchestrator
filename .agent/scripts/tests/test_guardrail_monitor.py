#!/usr/bin/env python3
import unittest
import sys
from pathlib import Path

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev", "misc"]:
        sys.path.append(str(REPO_ROOT / ".agent" / "scripts" / domain))

import health.guardrail_monitor as guardrail_monitor

class TestGuardrailMonitor(unittest.TestCase):
    def test_check_budget(self):
        rules = {"limits": {"token_budget_per_task": 1000, "cost_limit_per_task_usd": 1.0}}
        
        # Within limits
        telemetry = {"total_tokens": 500, "total_cost_usd": 0.5}
        ok, msg = guardrail_monitor.check_budget(rules, telemetry)
        self.assertTrue(ok)
        
        # Token overrun
        telemetry = {"total_tokens": 1500, "total_cost_usd": 0.5}
        ok, msg = guardrail_monitor.check_budget(rules, telemetry)
        self.assertFalse(ok)
        self.assertIn("TOKEN BUDGET EXCEEDED", msg)
        
        # Cost overrun
        telemetry = {"total_tokens": 500, "total_cost_usd": 1.5}
        ok, msg = guardrail_monitor.check_budget(rules, telemetry)
        self.assertFalse(ok)
        self.assertIn("COST LIMIT EXCEEDED", msg)

    def test_is_command_match(self):
        # Case insensitive
        self.assertTrue(guardrail_monitor._is_command_match("RM -RF", "rm -rf /"))
        
        # Word boundary
        self.assertTrue(guardrail_monitor._is_command_match("rm", "rm file.txt"))
        self.assertFalse(guardrail_monitor._is_command_match("rm", "storm.py"))
        
        # Inside string search (grep, rg, etc)
        self.assertFalse(guardrail_monitor._is_command_match("rm", "grep rm file.txt"))

    def test_check_dangerous_command(self):
        rules = {
            "dangerous_operations": {
                "commands": {
                    "block": ["rm -rf /", "mkfs"],
                    "warn": ["rm"]
                }
            }
        }
        
        # Block
        level, msg = guardrail_monitor.check_dangerous_command(rules, "rm -rf /")
        self.assertEqual(level, "block")
        
        # Warn
        level, msg = guardrail_monitor.check_dangerous_command(rules, "rm test.txt")
        self.assertEqual(level, "warn")
        
        # Segment check (pipe)
        level, msg = guardrail_monitor.check_dangerous_command(rules, "ls | rm")
        self.assertEqual(level, "warn")

    def test_check_secret_leak(self):
        # AWS Key
        ok, msg = guardrail_monitor.check_secret_leak("export AWS_KEY=AKIA1234567890123456")
        self.assertTrue(ok)
        self.assertIn("SECRET DETECTED", msg)
        
        # Generic secret
        ok, msg = guardrail_monitor.check_secret_leak("curl -H 'Authorization: Bearer my-token-1234567890123456'")
        self.assertTrue(ok)
        
        # Safe
        ok, msg = guardrail_monitor.check_secret_leak("echo 'hello world'")
        self.assertFalse(ok)

    def test_check_protected_file(self):
        rules = {
            "dangerous_operations": {
                "files": {
                    "protected": [".env", "id_rsa", "config/secrets.yaml"]
                }
            }
        }
        
        # Protected
        level, msg = guardrail_monitor.check_protected_file(rules, ".env")
        self.assertEqual(level, "protected")
        
        # Protected in subfolder
        level, msg = guardrail_monitor.check_protected_file(rules, "sub/.env")
        self.assertEqual(level, "protected")
        
        # Safe
        level, msg = guardrail_monitor.check_protected_file(rules, "README.md")
        self.assertEqual(level, "ok")

if __name__ == "__main__":
    unittest.main()
