#!/usr/bin/env python3

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    import sys
    from pathlib import Path
    SCRIPTS_DIR = Path(__file__).resolve().parents[1]
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.append(str(SCRIPTS_DIR))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev"]:
        d_path = str(SCRIPTS_DIR / domain)
        if d_path not in sys.path:
            sys.path.append(d_path)

import os
import sys
import subprocess
from pathlib import Path

# Antigravity Standard: Path Resolution
sys.path.append(str(Path(__file__).resolve().parent.parent))
from lib.common import load_json_safe, save_json_atomic
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
        ("Security", "python3 .agent/scripts/health/security_scan.py --target ."),
        ("Documentation Drift", "python3 .agent/scripts/health/drift_detector.py"),
        ("Linguistic Compliance", "python3 .agent/scripts/dev/linguistic_guardian.py"),
        # ("Full Verification", "python3 .agent/scripts/dev/verify_all.py ."), # Requires URL
        # ("Linting", "python3 .agent/scripts/lint_runner.py ."),
        # ("Tests", "python3 .agent/scripts/test_runner.py .")
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
