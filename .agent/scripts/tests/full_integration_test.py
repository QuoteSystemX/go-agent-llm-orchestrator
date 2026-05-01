import sys
import os
import json
import unittest
from pathlib import Path
from datetime import datetime, timedelta

# Add scripts to path
SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(SCRIPTS_DIR))

from lib.paths import REPO_ROOT, WATCHDOG_RULES_PATH, TELEMETRY_PATH, LESSONS_PATH
from lib.common import load_json_safe, save_json_atomic
import guardrail_monitor
import experience_distiller
import bus_manager
import checklist

class FullIntegrationTest(unittest.TestCase):
    def setUp(self):
        # Backup existing config if needed, or use a test sandbox
        # For this test, we'll work with the actual project files but carefully
        self.rules_backup = load_json_safe(WATCHDOG_RULES_PATH)
        self.telemetry_backup = load_json_safe(TELEMETRY_PATH)

    def tearDown(self):
        # Restore backups
        save_json_atomic(WATCHDOG_RULES_PATH, self.rules_backup)
        save_json_atomic(TELEMETRY_PATH, self.telemetry_backup)

    def test_01_paths_and_common(self):
        print("\nTesting Paths and Common Lib...")
        root = REPO_ROOT
        self.assertTrue((root / ".agent").exists())
        
        test_path = root / ".agent" / "test_tmp.json"
        data = {"test": "ok"}
        save_json_atomic(test_path, data)
        loaded = load_json_safe(test_path)
        self.assertEqual(loaded["test"], "ok")
        test_path.unlink()

    def test_02_guardrail_enhanced_parsing(self):
        print("Testing Guardrail Enhanced Parsing...")
        # Block 'rm -rf /'
        rules = {
            "dangerous_operations": {
                "commands": {"block": ["rm -rf /"], "warn": []}
            }
        }
        
        # Test direct
        res, msg = guardrail_monitor.check_dangerous_command(rules, "rm -rf /")
        self.assertEqual(res, "block")
        
        # Test pipe
        res, msg = guardrail_monitor.check_dangerous_command(rules, "echo hi | rm -rf /")
        self.assertEqual(res, "block")
        
        # Test subshell
        res, msg = guardrail_monitor.check_dangerous_command(rules, "ls $(rm -rf /)")
        self.assertEqual(res, "block")

    def test_03_secret_leak_detection(self):
        print("Testing Secret Leak Detection...")
        cmd = "curl -H 'Authorization: Bearer my-secret-token-1234567890'"
        detected, msg = guardrail_monitor.check_secret_leak(cmd)
        self.assertTrue(detected)
        self.assertIn("Bearer", msg)

        cmd_safe = "echo hello world"
        detected, msg = guardrail_monitor.check_secret_leak(cmd_safe)
        self.assertFalse(detected)

    def test_04_experience_global_search(self):
        print("Testing Experience Global Search...")
        # Create a dummy archive
        archive_dir = REPO_ROOT / "wiki" / "archive" / "experience"
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_file = archive_dir / "2020-01-01.md"
        
        with open(archive_file, "w", encoding="utf-8") as f:
            f.write("### [2020-01-01] [INFO] [test-skill] Ancient wisdom\n")
            
        res = experience_distiller.filter_by_skill("test-skill")
        self.assertIn("Ancient wisdom", res)
        self.assertIn("(including archives)", res)
        
        archive_file.unlink()

    def test_05_bus_telemetry_alerts(self):
        print("Testing Bus Telemetry Alerts...")
        # Set low budget
        rules = {"limits": {"token_budget_per_task": 100, "cost_limit_per_task_usd": 0.01}}
        save_json_atomic(WATCHDOG_RULES_PATH, rules)
        
        # We capture stdout to check for alert
        import io
        from contextlib import redirect_stdout
        
        f = io.StringIO()
        with redirect_stdout(f):
            bus_manager.push("t1", "telemetry", "tester", '{"total_tokens": 500, "total_cost_usd": 1.0}')
        
        output = f.getvalue()
        self.assertIn("BUS ALERT", output)

    def test_06_checklist_schema_validation(self):
        print("Testing Checklist Schema Validation...")
        # This will test if the schema check works
        ok, msg = checklist.check_watchdog_schema()
        # If jsonschema is not installed it returns True, "jsonschema not installed"
        # If it is installed, it should be True, "Validation successful" for our valid backup
        self.assertTrue(ok)

    def test_07_weighted_search(self):
        print("Testing Weighted Search...")
        # Create a lesson with specific keywords
        with open(LESSONS_PATH, "a", encoding="utf-8") as f:
            f.write("\n### [2026-01-01] [INFO] [test] The magic word is xyzzy\n")
        
        res = experience_distiller.search_lessons("magic xyzzy")
        self.assertIn("xyzzy", res)
        self.assertIn("Top", res)

    def test_08_adr_generation(self):
        print("Testing ADR Generation...")
        from generate_adr import generate_adr
        msg = generate_adr("Test Decision", "The context is testing.", "The decision is to pass.")
        self.assertIn("ADR created", msg)
        # Cleanup
        import re
        match = re.search(r'ADR-(\d+)-test-decision.md', msg)
        if match:
            (REPO_ROOT / "wiki" / "decisions" / match.group(0)).unlink()

    def test_09_health_score(self):
        print("Testing Health Score...")
        from status_report import calculate_health
        score, metrics = calculate_health()
        self.assertGreaterEqual(score, 0)
        self.assertIn("Drift", metrics)

if __name__ == "__main__":
    unittest.main()
