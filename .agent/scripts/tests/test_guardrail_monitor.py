#!/usr/bin/env python3
"""Tests for guardrail_monitor.py — block/warn/ok matching and budget checks."""
import sys
import unittest
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from guardrail_monitor import (
    check_budget,
    check_dangerous_command,
    check_protected_file,
    _is_command_match,
    _is_inside_string_search,
)


SAMPLE_RULES = {
    "limits": {
        "token_budget_per_task": 100000,
        "cost_limit_per_task_usd": 2.0,
    },
    "dangerous_operations": {
        "commands": {
            "block": [
                "rm -rf /",
                "DROP DATABASE",
                "git push --force origin main",
                "curl | bash",
                "echo $PASSWORD",
                "cat .env",
            ],
            "warn": [
                "rm -rf",
                "DROP TABLE",
                "DELETE FROM",
                "git push --force",
                "terraform destroy",
            ],
        },
        "files": {
            "protected": [
                ".env",
                ".env.*",
                "go.mod",
                "*.pem",
                ".agent/config/*",
            ],
        },
    },
}


class TestBudgetCheck(unittest.TestCase):
    def test_within_budget(self):
        ok, msg = check_budget(SAMPLE_RULES, {"total_tokens": 50000, "total_cost_usd": 1.0})
        self.assertTrue(ok)

    def test_token_exceeded(self):
        ok, msg = check_budget(SAMPLE_RULES, {"total_tokens": 150000, "total_cost_usd": 0.5})
        self.assertFalse(ok)
        self.assertIn("TOKEN BUDGET", msg)

    def test_cost_exceeded(self):
        ok, msg = check_budget(SAMPLE_RULES, {"total_tokens": 1000, "total_cost_usd": 5.0})
        self.assertFalse(ok)
        self.assertIn("COST LIMIT", msg)

    def test_empty_telemetry(self):
        ok, msg = check_budget(SAMPLE_RULES, {})
        self.assertTrue(ok)


class TestDangerousCommand(unittest.TestCase):
    def test_block_rm_rf_root(self):
        level, _ = check_dangerous_command(SAMPLE_RULES, "rm -rf /")
        self.assertEqual(level, "block")

    def test_block_drop_database(self):
        level, _ = check_dangerous_command(SAMPLE_RULES, "psql -c 'DROP DATABASE production'")
        self.assertEqual(level, "block")

    def test_block_force_push_main(self):
        level, _ = check_dangerous_command(SAMPLE_RULES, "git push --force origin main")
        self.assertEqual(level, "block")

    def test_warn_rm_rf_directory(self):
        level, _ = check_dangerous_command(SAMPLE_RULES, "rm -rf /tmp/old_data")
        self.assertEqual(level, "warn")

    def test_warn_terraform_destroy(self):
        level, _ = check_dangerous_command(SAMPLE_RULES, "terraform destroy -auto-approve")
        self.assertEqual(level, "warn")

    def test_ok_safe_command(self):
        level, _ = check_dangerous_command(SAMPLE_RULES, "go test ./...")
        self.assertEqual(level, "ok")

    def test_ok_ls_command(self):
        level, _ = check_dangerous_command(SAMPLE_RULES, "ls -la")
        self.assertEqual(level, "ok")

    def test_no_false_positive_grep_drop(self):
        """grep 'DROP TABLE' in a doc should NOT trigger warn."""
        level, _ = check_dangerous_command(SAMPLE_RULES, 'grep "DROP TABLE" documentation.md')
        self.assertEqual(level, "ok")

    def test_no_false_positive_echo_password(self):
        """cat .env should block, but grep inside quotes should be ok."""
        level, _ = check_dangerous_command(SAMPLE_RULES, 'grep "cat .env" script.sh')
        self.assertEqual(level, "ok")


class TestProtectedFile(unittest.TestCase):
    def test_env_protected(self):
        level, _ = check_protected_file(SAMPLE_RULES, ".env")
        self.assertEqual(level, "protected")

    def test_env_production_protected(self):
        level, _ = check_protected_file(SAMPLE_RULES, ".env.production")
        self.assertEqual(level, "protected")

    def test_go_mod_protected(self):
        level, _ = check_protected_file(SAMPLE_RULES, "go.mod")
        self.assertEqual(level, "protected")

    def test_pem_protected(self):
        level, _ = check_protected_file(SAMPLE_RULES, "server.pem")
        self.assertEqual(level, "protected")

    def test_agent_config_protected(self):
        level, _ = check_protected_file(SAMPLE_RULES, ".agent/config/router_rules.json")
        self.assertEqual(level, "protected")

    def test_normal_file_ok(self):
        level, _ = check_protected_file(SAMPLE_RULES, "src/main.go")
        self.assertEqual(level, "ok")

    def test_readme_ok(self):
        level, _ = check_protected_file(SAMPLE_RULES, "README.md")
        self.assertEqual(level, "ok")


class TestCommandMatchHelper(unittest.TestCase):
    def test_multiword_match(self):
        self.assertTrue(_is_command_match("rm -rf /", "rm -rf /"))

    def test_single_word_boundary(self):
        self.assertTrue(_is_command_match("mkfs", "sudo mkfs.ext4 /dev/sda"))

    def test_inside_grep_no_match(self):
        self.assertFalse(_is_command_match("DROP TABLE", 'grep "DROP TABLE" file.sql'))


if __name__ == "__main__":
    unittest.main()
