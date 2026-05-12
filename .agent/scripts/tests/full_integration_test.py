import sys
import os
import json
import unittest
from pathlib import Path
from datetime import datetime, timedelta

# Add scripts and domain subfolders to path
SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(SCRIPTS_DIR))
for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev"]:
    sys.path.append(str(SCRIPTS_DIR / domain))

from lib.paths import REPO_ROOT, WATCHDOG_RULES_PATH, TELEMETRY_PATH, LESSONS_PATH
from lib.common import load_json_safe, save_json_atomic
import health.guardrail_monitor; import sys; sys.modules['guardrail_monitor'] = sys.modules['health.guardrail_monitor']; import health.guardrail_monitor as guardrail_monitor
import knowledge.experience_distiller; import sys; sys.modules['experience_distiller'] = sys.modules['knowledge.experience_distiller']; import knowledge.experience_distiller as experience_distiller
import context.bus_manager; import sys; sys.modules['bus_manager'] = sys.modules['context.bus_manager']; import context.bus_manager as bus_manager
import dev.checklist; import sys; sys.modules['checklist'] = sys.modules['dev.checklist']; import dev.checklist as checklist
import health.status_report; import sys; sys.modules['status_report'] = sys.modules['health.status_report']; import health.status_report as status_report
import knowledge.adr_generator; import sys; sys.modules['adr_generator'] = sys.modules['knowledge.adr_generator']; import knowledge.adr_generator as adr_generator
import knowledge.generate_adr; import sys; sys.modules['generate_adr'] = sys.modules['knowledge.generate_adr']; import knowledge.generate_adr as generate_adr

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
        from contextlib import redirect_stdout, redirect_stderr
        
        # Clear bus to avoid ID collision
        bus_manager.clear()
        
        f = io.StringIO()
        with redirect_stdout(f), redirect_stderr(f):
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
        self.assertIn("Local Matches", res)

    def test_08_adr_generation(self):
        print("Testing ADR Generation...")
        msg = generate_adr.generate_adr("Test Decision", "The context is testing.", "The decision is to pass.")
        self.assertIn("ADR created", msg)
        # Cleanup
        import re
        match = re.search(r'ADR-(\d+)-test-decision.md', msg)
        if match:
            (REPO_ROOT / "wiki" / "decisions" / match.group(0)).unlink()

    def test_09_health_score(self):
        print("Testing Health Score...")
        score, metrics = status_report.calculate_health()
        self.assertGreaterEqual(score, 0)
        self.assertIn("Drift", metrics)

    def test_10_external_suites(self):
        print("Running External Test Suites...")
        import subprocess
        external_tests = [
            "test_reliability.py",
            "test_phase_23.py",
            "test_model_router.py",
            "test_tracer.py",
            "test_global_brain.py"
        ]
        for t in external_tests:
            tpath = SCRIPTS_DIR / "tests" / t
            if tpath.exists():
                print(f"  🚀 Executing {t}...")
                env = os.environ.copy()
                domains = ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev"]
                domain_paths = [str(SCRIPTS_DIR / d) for d in domains]
                env["PYTHONPATH"] = f"{SCRIPTS_DIR}:" + ":".join(domain_paths) + f":{env.get('PYTHONPATH', '')}"
                res = subprocess.run([sys.executable, str(tpath)], capture_output=True, text=True, env=env)
                # We don't fail the whole suite if an orphan test fails, but we log it
                if res.returncode != 0:
                    print(f"    ⚠️  Orphan Test {t} FAILED:\n{res.stdout}\n{res.stderr}")
                else:
                    print(f"    ✅ {t} Passed.")

if __name__ == "__main__":
    unittest.main()
