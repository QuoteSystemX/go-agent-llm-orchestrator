#!/usr/bin/env python3
"""Sandbox Runner — Safe Code Execution Environment.

Analyzes code for dangerous patterns and executes it in a restricted environment.
Part of the Unified Cardinal Enhancements Phase 3.
"""
import sys
import os
import ast
import subprocess
import tempfile
from pathlib import Path

DANGEROUS_IMPORTS = ["os", "subprocess", "shutil", "socket", "requests", "urllib", "pty", "platform"]

def analyze_code(source):
    """Perform static analysis to detect dangerous imports or calls."""
    try:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in DANGEROUS_IMPORTS:
                        return False, f"Dangerous import detected: {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.module in DANGEROUS_IMPORTS:
                    return False, f"Dangerous import detected: {node.module}"
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in ["eval", "exec", "open"]:
                    return False, f"Dangerous function call detected: {node.func.id}"
        return True, "Code looks safe."
    except Exception as e:
        return False, f"Failed to parse code: {e}"

def run_in_sandbox(source):
    """Execute code in a restricted temporary environment."""
    safe, msg = analyze_code(source)
    if not safe:
        print(f"🛑 SANDBOX VETO: {msg}")
        return False

    print("🧪 Executing in sandbox...")
    with tempfile.TemporaryDirectory() as tmpdir:
        script_file = Path(tmpdir) / "sandbox_script.py"
        script_file.write_text(source)
        
        try:
            # Run with restricted env and timeout
            result = subprocess.run(
                [sys.executable, str(script_file)],
                capture_output=True,
                text=True,
                timeout=5,
                env={"PYTHONPATH": os.getcwd()} # Allow local imports but restrict others
            )
            print("--- STDOUT ---")
            print(result.stdout)
            if result.stderr:
                print("--- STDERR ---")
                print(result.stderr)
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            print("❌ SANDBOX ERROR: Execution timed out (Possible infinite loop or heavy task).")
            return False
        except Exception as e:
            print(f"❌ SANDBOX ERROR: {e}")
            return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 sandbox_runner.py <path_to_script> or pipe code to stdin")
        sys.exit(1)
    
    path = sys.argv[1]
    if os.path.exists(path):
        with open(path, "r") as f:
            code = f.read()
    else:
        code = path # Treat as raw code
        
    success = run_in_sandbox(code)
    sys.exit(0 if success else 1)
