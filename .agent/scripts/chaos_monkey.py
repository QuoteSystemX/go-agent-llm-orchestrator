#!/usr/bin/env python3
import os
import sys
import random
from pathlib import Path
import time

sys.path.append(str(Path(__file__).resolve().parent))
from lib.common import load_json_safe, save_json_atomic
from lib.paths import REPO_ROOT

def break_something():
    """Introduces a documentation drift defect."""
    new_script = REPO_ROOT / ".agent" / "scripts" / "extremely_unique_chaos_script.py"
    print(f"🐒 Chaos: Creating undocumented script {new_script.name}")
    new_script.write_text('"""Extremely Unique Chaos Script — Used to test doc_healer resilience."""\nprint("Chaos!")\n', encoding="utf-8")
    return new_script

def main():
    print("🔥 AGENTIC CHAOS MONKEY STARTING...")
    target_file = break_something()
    
    print("⏳ Waiting for Immune System (5s)...")
    time.sleep(5)
    
    print("🏥 Running Doc Healer to verify recovery...")
    try:
        subprocess.run("python3 .agent/scripts/doc_healer.py", shell=True, check=True, cwd=REPO_ROOT)
    except Exception as e:
        print(f"❌ Doc Healer failed: {e}")
        sys.exit(1)
        
    # Check if ARCHITECTURE.md now contains the script
    arch_path = REPO_ROOT / ".agent" / "ARCHITECTURE.md"
    content = arch_path.read_text(encoding="utf-8")
    if "extremely_unique_chaos_script.py" in content:
        print(f"✅ SYSTEM RECOVERED: {target_file.name} is now documented.")
        # Cleanup
        target_file.unlink()
    else:
        print(f"❌ SYSTEM FAILED TO RECOVER: {target_file.name} still undocumented.")
        target_file.unlink()
        sys.exit(1)

if __name__ == "__main__":
    import subprocess
    main()
