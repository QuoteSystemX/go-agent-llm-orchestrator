#!/usr/bin/env python3
import os
import sys
import subprocess
from pathlib import Path

# Antigravity Standard: Path Resolution
sys.path.append(str(Path(__file__).resolve().parent))
from lib.common import load_json_safe, save_json_atomic, log_event
from lib.paths import REPO_ROOT

def run_check(name, command):
    print(f"🔍 Running {name}...")
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, cwd=REPO_ROOT)
        if result.returncode == 0:
            print(f"✅ {name} passed.")
            return True, result.stdout
        else:
            print(f"❌ {name} failed.")
            return False, result.stderr + "\n" + result.stdout
    except Exception as e:
        print(f"⚠️ Error running {name}: {e}")
        return False, str(e)

def main():
    checks = [
        ("Linting", "python3 .agent/scripts/lint_runner.py ."),
        ("Security", "python3 .agent/scripts/security_scan.py ."),
        ("Documentation Drift", "python3 .agent/scripts/drift_detector.py"),
        ("Tests", "python3 .agent/scripts/test_runner.py .")
    ]
    
    failed = []
    reports = []
    
    for name, cmd in checks:
        success, output = run_check(name, cmd)
        if not success:
            failed.append(name)
        reports.append(f"### {name}\n{output[:500]}...")
        
    print("\n" + "="*40)
    if not failed:
        print("🎉 ALL PR AUDIT CHECKS PASSED!")
        sys.exit(0)
    else:
        print(f"🚫 PR AUDIT FAILED: {', '.join(failed)}")
        print("\n".join(reports))
        sys.exit(1)

if __name__ == "__main__":
    main()
