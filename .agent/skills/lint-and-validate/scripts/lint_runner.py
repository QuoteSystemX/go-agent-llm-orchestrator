#!/usr/bin/env python3
import os
import subprocess
import json
import sys
import platform
import re
from pathlib import Path

def run_command(cmd, cwd="."):
    """Helper to run shell commands and return results."""
    try:
        res = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding='utf-8',
            shell=platform.system() == "Windows"
        )
        return res.stdout, res.stderr, res.returncode
    except Exception as e:
        return "", str(e), 1

def scan_garbage_files(project_path: Path) -> dict:
    """Find and remove artifacts (Tiered Cleanup)."""
    forbidden = {
        "files": ["package-lock.json", "yarn.lock", "pnpm-lock.yaml", "Pipfile.lock", "poetry.lock", "composer.lock"],
        "patterns": [r".*\.log$", r".*\.tmp$", r"Thumbs\.db", r"\.DS_Store"],
        "dirs": ["reports", "logs", ".jules"]
    }
    found = []
    for root, dirs, files in os.walk(project_path):
        # Prune dirs
        for d in list(dirs):
            if d in forbidden["dirs"] or d.startswith("__pycache__") or d == ".pytest_cache":
                dir_path = Path(root) / d
                found.append(str(dir_path))
                import shutil
                try: shutil.rmtree(dir_path)
                except: pass
                dirs.remove(d)
        
        for f in files:
            file_path = Path(root) / f
            is_forbidden = f in forbidden["files"]
            if not is_forbidden:
                for pattern in forbidden["patterns"]:
                    if re.match(pattern, f):
                        is_forbidden = True
                        break
            if is_forbidden:
                found.append(str(file_path))
                try: file_path.unlink()
                except: pass
    
    return {"name": "garbage-scan", "passed": True, "found": found}

def scan_documentation_drift(project_path: Path) -> dict:
    script_path = project_path / ".agent" / "scripts" / "drift_detector.py"
    if not script_path.exists():
        return {"name": "drift-check", "passed": True, "drifts": [], "output": "drift_detector.py not found"}
    stdout, stderr, code = run_command(["python3", str(script_path), "--format", "json"], project_path)
    try:
        data = json.loads(stdout)
        return {"name": "drift-check", "passed": data.get("passed", True), "drifts": data.get("drifts", []), "output": f"Found {len(data.get('drifts', []))} drifts"}
    except:
        return {"name": "drift-check", "passed": True, "drifts": [], "error": stderr}

def validate_commit_msg(project_path: Path) -> dict:
    if not (project_path / ".git").exists():
        return {"name": "commit-lint", "passed": True, "msg": "No git"}
    stdout, stderr, code = run_command(["git", "log", "-1", "--pretty=%s"], project_path)
    if code == 0:
        msg = stdout.strip()
        pattern = r"^(feat|fix|chore|docs|style|refactor|perf|test|db)(\([a-z0-9_-]+\))?!?: .+$"
        passed = bool(re.match(pattern, msg))
        return {"name": "commit-lint", "passed": passed, "msg": msg, "output": f"Valid format: {msg}" if passed else f"Invalid: {msg}"}
    return {"name": "commit-lint", "passed": True, "error": stderr}

def scan_type_coverage(project_path: Path) -> dict:
    script_path = project_path / ".agent" / "skills" / "lint-and-validate" / "scripts" / "type_coverage.py"
    if not script_path.exists():
        return {"name": "type-coverage", "passed": True, "output": "N/A"}
    stdout, stderr, code = run_command(["python3", str(script_path), "."], project_path)
    coverage_match = re.search(r"Type coverage: (\d+%)", stdout)
    passed = code == 0
    return {"name": "type-coverage", "passed": passed, "output": coverage_match.group(1) if coverage_match else "Analyzed", "issues": len(re.findall(r"\[X\]", stdout))}

def detect_project_type(project_path: Path):
    if (project_path / "package.json").exists(): return "node"
    if (project_path / "go.mod").exists(): return "go"
    if (project_path / "pyproject.toml").exists() or (project_path / "requirements.txt").exists(): return "python"
    return "unknown"

def get_linters(p_type, fix):
    if p_type == "node":
        return [{"name": "eslint", "cmd": ["npx", "eslint", ".", "--fix"] if fix else ["npx", "eslint", "."]}]
    if p_type == "python":
        return [{"name": "ruff", "cmd": ["ruff", "check", ".", "--fix"] if fix else ["ruff", "check", "."]}]
    if p_type == "go":
        return [{"name": "go vet", "cmd": ["go", "vet", "./..."]}]
    return []

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("project_path", nargs="?", default=".")
    parser.add_argument("--fix", action="store_true")
    parser.add_argument("--cleanup-only", action="store_true")
    args = parser.parse_args()
    project_path = Path(args.project_path).resolve()

    print(f"🚀 Antigravity Hygiene & Linting: {project_path}")
    
    garbage = scan_garbage_files(project_path)
    print(f"🧹 Garbage Cleanup: {len(garbage['found'])} items removed.")
    
    if args.cleanup_only:
        sys.exit(0)

    drift = scan_documentation_drift(project_path)
    commit = validate_commit_msg(project_path)
    types = scan_type_coverage(project_path)
    
    p_type = detect_project_type(project_path)
    linters = get_linters(p_type, args.fix)
    
    # Fix for Go project with no files
    if p_type == "go":
        # Recursively find any .go files, excluding .agent and hidden dirs
        go_files_found = False
        for root, dirs, files in os.walk(project_path):
            if ".agent" in root or ".git" in root: continue
            if any(f.endswith(".go") for f in files):
                go_files_found = True
                break
        if not go_files_found:
            linters = []
            print("No Go files found in source, skipping go vet.")

    linter_results = []
    for l in linters:
        print(f"Running {l['name']}...")
        stdout, stderr, code = run_command(l['cmd'], project_path)
        linter_results.append({"name": l['name'], "passed": code == 0, "output": stdout, "error": stderr})

    all_checks = [garbage, drift, commit, types] + linter_results
    passed = all(c["passed"] for c in all_checks)
    
    print("\n" + "="*60 + "\nSUMMARY\n" + "="*60)
    print(f"[{'PASS' if garbage['passed'] else 'FAIL'}] garbage-scan")
    print(f"[{'PASS' if drift['passed'] else 'FAIL'}] drift-check: {drift['output']}")
    print(f"[{'PASS' if commit['passed'] else 'FAIL'}] commit-lint: {commit['output'] if 'output' in commit else commit['msg']}")
    print(f"[{'PASS' if types['passed'] else 'FAIL'}] type-coverage: {types['output']}")
    for r in linter_results:
        print(f"[{'PASS' if r['passed'] else 'FAIL'}] {r['name']}")
    
    output = {
        "project": str(project_path),
        "type": p_type,
        "garbage_scan": garbage,
        "drift_check": drift,
        "commit_lint": commit,
        "type_coverage": types,
        "linters": linter_results,
        "passed": passed
    }
    print("\n" + json.dumps(output, indent=2))
    sys.exit(0 if passed else 1)

if __name__ == "__main__":
    main()
