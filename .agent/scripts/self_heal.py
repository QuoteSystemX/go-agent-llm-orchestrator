#!/usr/bin/env python3
import subprocess
import sys
import json
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
LINT_RUNNER = REPO_ROOT / ".agent" / "skills" / "lint-and-validate" / "scripts" / "lint_runner.py"

def run_self_heal(project_path):
    print(f"🔧 Starting Self-Healing process for: {project_path}")
    
    if not LINT_RUNNER.exists():
        print(f"❌ Error: {LINT_RUNNER} not found.")
        return False

    # Run lint_runner with --fix
    cmd = ["python3", str(LINT_RUNNER), str(project_path), "--fix"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        
        # The output of lint_runner ends with a JSON block
        output = res.stdout.strip()
        print(output)
        
        if res.returncode == 0:
            print("\n✅ Self-Healing successful! All auto-fixable issues resolved.")
            return True
        else:
            print("\n⚠️  Self-Healing completed with some remaining issues.")
            return False
            
    except Exception as e:
        print(f"❌ Error during self-heal: {str(e)}")
        return False

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    project_path = Path(target).resolve()
    success = run_self_heal(project_path)
    sys.exit(0 if success else 1)
