#!/usr/bin/env python3
"""
Ralph Loop - Autonomous & Atomic Self-Healing
=============================================

Runs a loop to detect linter/test failures, queries LLM with a clean context,
applies the suggested patch, verifies it, and commits directly to the active Git branch.
"""

import sys
import os
import argparse
import subprocess
import json
import re
from pathlib import Path

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev"]:
        sys.path.append(str(REPO_ROOT / ".agent" / "scripts" / domain))

from lib.llm_client import query_llm_safe

def run_cmd(cmd: list, cwd: Path = REPO_ROOT) -> tuple[int, str]:
    """Helper to run a shell command and capture return code and output."""
    env = os.environ.copy()
    env["GOPRIVATE"] = "github.com/QuoteSystemX/*"
    # Prevent pythonpath collision in sub-processes
    if "PYTHONPATH" in env:
        del env["PYTHONPATH"]
    try:
        res = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, env=env)
        return res.returncode, res.stdout + res.stderr
    except Exception as e:
        return -1, str(e)

def detect_failures() -> list[dict]:
    """Runs tests and linter audits to detect any failures to fix."""
    failures = []
    
    # 1. Run workspace go test
    print("🧪 Checking Go workspace tests...")
    code, output = run_cmd(["go", "test", "./..."])
    if code != 0:
        # Try to parse failing file name from output
        # e.g., "--- FAIL: TestFoo (0.00s)\n    foo_test.go:42: error"
        file_match = re.search(r"([\w_]+\.go):(\d+)", output)
        failing_file = file_match.group(1) if file_match else None
        
        # If we can't find a specific file, try to look at modified files or git status
        if not failing_file:
            git_code, git_out = run_cmd(["git", "status", "--porcelain"])
            for line in git_out.splitlines():
                if line.endswith(".go"):
                    failing_file = line.split()[-1]
                    break
        
        failures.append({
            "type": "test_failure",
            "language": "Go",
            "file": failing_file or "workspace",
            "error_msg": output[:1000]
        })
        
    # 2. Run Python/linter checklist
    print("🧹 Running master checklist...")
    code, output = run_cmd(["python3", ".agent/scripts/dev/checklist.py", "."])
    if code != 0:
        # Check linter debt metrics
        linter_metrics_file = REPO_ROOT / ".agent" / "bus" / "linter_debt_metrics.json"
        if linter_metrics_file.exists():
            try:
                metrics = json.loads(linter_metrics_file.read_text(encoding="utf-8"))
                if metrics.get("status") == "FAIL" or metrics.get("status") == "WARN":
                    failures.append({
                        "type": "linter_debt",
                        "language": "Universal",
                        "file": "linter_debt",
                        "error_msg": "Linter debt check failed: " + output[:500]
                    })
            except Exception:
                pass
                
        if not failures:
            failures.append({
                "type": "checklist_failure",
                "language": "Universal",
                "file": "checklist",
                "error_msg": output[:1000]
            })
            
    return failures

def run_ralph_loop(max_iterations: int, dry_run: bool):
    print(f"🚀 Starting Ralph Loop (Max Iterations: {max_iterations}, Dry Run: {dry_run})")
    
    for iteration in range(1, max_iterations + 1):
        print(f"\n--- 🔄 Iteration {iteration}/{max_iterations} ---")
        
        failures = detect_failures()
        if not failures:
            print("✅ No failures detected! Workspace is healthy.")
            break
            
        failure = failures[0]
        print(f"🚨 Found failure: {failure['type']} in {failure['file']}")
        
        # Decide which agent to target based on language/type
        agent_name = "go-specialist"
        if failure["language"] == "Python":
            agent_name = "python-specialist"
        elif failure["language"] == "Universal":
            agent_name = "orchestrator"
            
        target_file_path = None
        file_content = ""
        
        # Try to locate the file to fix
        if failure["file"] != "workspace" and failure["file"] != "linter_debt" and failure["file"] != "checklist":
            # Search for the file in the workspace
            for p in REPO_ROOT.rglob(failure["file"]):
                if p.is_file():
                    target_file_path = p
                    break
        
        # If we couldn't resolve a file, fall back to files modified in Git
        if not target_file_path:
            git_code, git_out = run_cmd(["git", "status", "--porcelain"])
            for line in git_out.splitlines():
                rel_path = line.split()[-1]
                p = REPO_ROOT / rel_path
                if p.is_file() and p.suffix in [".go", ".py", ".ts", ".js"]:
                    target_file_path = p
                    break
                    
        if target_file_path:
            rel_file = target_file_path.relative_to(REPO_ROOT)
            print(f"🎯 Target file identified: {rel_file}")
            file_content = target_file_path.read_text(encoding="utf-8")
        else:
            print("⚠️ Could not identify specific target file. Skipping this iteration.")
            continue
            
        # Write prompt for LLM
        prompt = (
            f"You are the {agent_name} agent. A build/test/lint failure occurred in the workspace.\n"
            f"Failing File: {rel_file}\n"
            f"Error Output:\n```\n{failure['error_msg']}\n```\n\n"
            f"Here is the current content of the file:\n"
            f"```\n{file_content}\n```\n\n"
            f"Provide the complete corrected code for this file. Return ONLY the new file content inside a single code block."
        )
        
        if dry_run:
            print(f"[DRY RUN] Would query LLM for fixing {rel_file}")
            continue
            
        print("🧠 Querying LLM for fix (fresh context)...")
        response, source, stats = query_llm_safe(prompt=prompt)
        
        # Extract file contents from code block
        code_blocks = re.findall(r"```(?:\w+)?\n(.*?)\n```", response, re.DOTALL)
        new_content = code_blocks[0] if code_blocks else response.strip()
        
        if not new_content or new_content.startswith("❌"):
            print("❌ Failed to parse valid correction from LLM.")
            continue
            
        # Apply patch
        print(f"💾 Applying patch to {rel_file}...")
        backup_content = target_file_path.read_text(encoding="utf-8")
        target_file_path.write_text(new_content, encoding="utf-8")
        
        # Verify fix
        print("🧪 Verifying patch...")
        verify_failures = detect_failures()
        
        # Check if the failure we were fixing is resolved
        resolved = True
        for vf in verify_failures:
            if vf["file"] == failure["file"] or (target_file_path.name in vf["error_msg"] if target_file_path else False):
                resolved = False
                break
                
        if resolved:
            print(f"🎉 Fix successful! Committing to the current branch...")
            run_cmd(["git", "add", str(target_file_path)])
            commit_msg = f"agent: auto-fix {failure['type']} in {rel_file.name}"
            run_cmd(["git", "commit", "-m", commit_msg])
            print("✅ Committed successfully.")
            
            # Record success lesson to LESSONS_LEARNED.md
            lessons_file = REPO_ROOT / "LESSONS_LEARNED.md"
            if lessons_file.exists():
                try:
                    entry = f"\n### [{Path(rel_file).name}] [{failure['type']}] [SUCCESS] - {commit_msg}\n"
                    with open(lessons_file, "a", encoding="utf-8") as lf:
                        lf.write(entry)
                except Exception:
                    pass
        else:
            print("❌ Verification failed. Rolling back patch...")
            target_file_path.write_text(backup_content, encoding="utf-8")
            
            # Record failure lesson to LESSONS_LEARNED.md
            lessons_file = REPO_ROOT / "LESSONS_LEARNED.md"
            if lessons_file.exists():
                try:
                    entry = f"\n### [{Path(rel_file).name}] [{failure['type']}] [FAIL] - LLM failed to fix: {failure['error_msg'][:100]}\n"
                    with open(lessons_file, "a", encoding="utf-8") as lf:
                        lf.write(entry)
                except Exception:
                    pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ralph Loop autonomous code corrector.")
    parser.add_argument("--iterations", type=int, default=3, help="Max loop iterations")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without LLM calls or git commits")
    args = parser.parse_args()
    
    run_ralph_loop(args.iterations, args.dry_run)
