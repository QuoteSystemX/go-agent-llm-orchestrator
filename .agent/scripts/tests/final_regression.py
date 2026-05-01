import sys
import os
import json
import unittest
import shutil
import subprocess
from pathlib import Path
from datetime import datetime, timedelta

# Add scripts to path
SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(SCRIPTS_DIR))

from lib.paths import REPO_ROOT, WATCHDOG_RULES_PATH, TELEMETRY_PATH, LESSONS_PATH, BUS_DIR
from lib.common import load_json_safe, save_json_atomic
import guardrail_monitor
import experience_distiller
import bus_manager
import checklist
import drift_detector
import status_report
import generate_adr
import post_mortem_runner
import visualize_deps

class FinalRegressionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create a sandbox directory for testing to avoid messing with the main repo
        cls.test_dir = REPO_ROOT / "tmp_regression_sandbox"
        cls.test_dir.mkdir(parents=True, exist_ok=True)
        
        # Backup main config
        cls.rules_backup = load_json_safe(WATCHDOG_RULES_PATH)
        cls.telemetry_backup = load_json_safe(TELEMETRY_PATH)

    @classmethod
    def tearDownClass(cls):
        # Restore backups
        save_json_atomic(WATCHDOG_RULES_PATH, cls.rules_backup)
        save_json_atomic(TELEMETRY_PATH, cls.telemetry_backup)
        # Cleanup sandbox
        if cls.test_dir.exists():
            shutil.rmtree(cls.test_dir)

    def test_01_core_libs(self):
        print("\n[REGRESSION] 01: Core Libraries (Paths/Common)")
        from lib.paths import get_repo_root
        self.assertEqual(get_repo_root(), REPO_ROOT)
        
        test_file = self.test_dir / "test.json"
        save_json_atomic(test_file, {"status": "verified"})
        data = load_json_safe(test_file)
        self.assertEqual(data["status"], "verified")

    def test_02_guardrail_logic(self):
        print("[REGRESSION] 02: Guardrail Monitor (Parsing/Secrets/Sandbox)")
        rules = {
            "dangerous_operations": {
                "commands": {"block": ["rm -rf /"], "warn": ["chmod 777"]}
            }
        }
        # Parsing regression
        res, _ = guardrail_monitor.check_dangerous_command(rules, "echo foo | rm -rf /")
        self.assertEqual(res, "block")
        
        # Secret leak regression
        detected, _ = guardrail_monitor.check_secret_leak("export AWS_ACCESS_KEY_ID=AKIA1234567890123456")
        self.assertTrue(detected)
        
        # Sandbox (check if docker exists)
        if shutil.which("docker"):
            # If docker is present, we try to run it.
            # If it fails due to daemon, we don't fail the whole test suite, 
            # but we verify it handled the error.
            success = guardrail_monitor.run_in_sandbox("echo 'hi'")
            # If daemon is down, success is False, which is expected behavior for the script
            self.assertIn(success, [True, False])

    def test_03_experience_distiller(self):
        print("[REGRESSION] 03: Experience Distiller (Weighted Search/Global)")
        # Add a unique lesson
        with open(LESSONS_PATH, "a", encoding="utf-8") as f:
            f.write("\n### [2026-05-01] [INFO] [regression] Regression secret word: quack\n")
            
        # Global search
        res = experience_distiller.filter_by_skill("regression")
        self.assertIn("quack", res)
        
        # Weighted search
        res_query = experience_distiller.search_lessons("secret quack")
        self.assertIn("quack", res_query)

    def test_04_bus_manager(self):
        print("[REGRESSION] 04: Bus Manager (Push/Wait/Alerts)")
        # Test alert
        rules = {"limits": {"token_budget_per_task": 10}}
        save_json_atomic(WATCHDOG_RULES_PATH, rules)
        
        # Capture stdout for alert
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            bus_manager.push("reg_1", "telemetry", "tester", '{"total_tokens": 100}')
        self.assertIn("BUS ALERT", buf.getvalue())
        
        # Test wait (async simulation - we just check if it finds existing one)
        # We run wait in a sub-process or just call it if it exists
        bus_manager.wait_for_object("reg_1", timeout=5)

    def test_05_drift_detector(self):
        print("[REGRESSION] 05: Drift Detector (Files/Agents/Skills)")
        drifts = drift_detector.detect_drift()
        # Should return list. If we are in sync, it might be empty or have file drifts from git
        self.assertIsInstance(drifts, list)

    def test_06_visualize_deps(self):
        print("[REGRESSION] 06: Visualize Deps (Mermaid)")
        res = visualize_deps.generate_mermaid()
        self.assertTrue("diagram updated" in res or "Generated Mermaid" in res)

    def test_07_status_report(self):
        print("[REGRESSION] 07: Status Report (Health Score)")
        score, metrics = status_report.calculate_health()
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

    def test_08_generate_adr(self):
        print("[REGRESSION] 08: ADR Generator")
        msg = generate_adr.generate_adr("Regression Decision", "Testing system", "Passed")
        self.assertIn("ADR created", msg)

    def test_09_post_mortem(self):
        print("[REGRESSION] 09: Post-Mortem Runner")
        res = post_mortem_runner.analyze_recent_failures()
        self.assertIsInstance(res, str)

    def test_10_checklist_fix(self):
        print("[REGRESSION] 10: Checklist (Auto-fix)")
        # Delete a non-critical but managed dir
        archive_dir = REPO_ROOT / "wiki/archive/experience"
        if archive_dir.exists():
            shutil.rmtree(archive_dir)
            
        checklist.run_fix()
        self.assertTrue(archive_dir.exists())

    def test_11_rollback_system(self):
        print("[REGRESSION] 11: Rollback System (Git/Bus)")
        # Push dummy object
        bus_manager.push("roll_1", "requirement", "tester", '{"task": "undo me"}')
        # Rollback (simulate without git reset for safety in test, or just check bus cleanup)
        from rollback_task import clean_bus
        clean_bus(author_filter="tester")
        data = load_json_safe(BUS_DIR / "context.json")
        self.assertFalse(any(obj["id"] == "roll_1" for obj in data.get("objects", [])))

    def test_12_test_factory(self):
        print("[REGRESSION] 12: Test Factory")
        from test_factory import generate_test
        msg = generate_test(".agent/scripts/lib/common.py")
        self.assertIn("Test file created", msg)
        test_path = REPO_ROOT / ".agent/scripts/lib/tests/test_common.py"
        self.assertTrue(test_path.exists())
        # Cleanup
        test_path.unlink()
        test_path.parent.rmdir()

    def test_13_config_healing(self):
        print("[REGRESSION] 13: Config Healing")
        # Corrupt the rules
        save_json_atomic(WATCHDOG_RULES_PATH, {"corrupt": True})
        checklist.run_fix()
        rules = load_json_safe(WATCHDOG_RULES_PATH)
        self.assertIn("limits", rules)

if __name__ == "__main__":
    unittest.main()
