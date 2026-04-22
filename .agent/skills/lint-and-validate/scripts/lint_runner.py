#!/usr/bin/env python3
"""
Lint Runner - Unified linting, type checking, and workspace cleanup validation.
Runs appropriate linters based on project type.
Also checks for forbidden garbage files that must never appear in PRs.

Usage:
    python lint_runner.py <project_path>

Supports:
    - Node.js: npm run lint, npx tsc --noEmit
    - Python: ruff check, mypy
"""

import subprocess
import sys
import json
import platform
import shutil
from pathlib import Path
from datetime import datetime

# Fix Windows console encoding
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except:
    pass


# Garbage file tiers:
# AUTO_DELETE  — OS/editor trash, always safe to delete silently
# SOFT_DELETE  — Agent artifacts (*.orig, *.diff, PLAN.md) — delete + create [CHORE] task
# WARN_ONLY    — Files that might be intentional (*.log, *.tmp) — report only

AUTO_DELETE_PATTERNS = [
    ".DS_Store", "Thumbs.db",
    "*.pyc", "*.pyo",
    "*~", "*.swp", "*.swo",
]
AUTO_DELETE_DIRS = ["__pycache__"]

SOFT_DELETE_PATTERNS = [
    "*.orig", "*.bak",
    "*.diff", "*.patch",
]
SOFT_DELETE_NAMES = {"PLAN.md"}  # Root-level exact matches

WARN_PATTERNS = [
    "*.log",
    "*.tmp",
]


def _delete_file(p: Path) -> bool:
    try:
        p.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def _create_chore_task(project_path: Path, auto_deleted: list, soft_deleted: list, warnings: list) -> str | None:
    """Create a [CHORE] task card in tasks/ describing what garbage was found and cleaned."""
    tasks_dir = project_path / "tasks"
    tasks_dir.mkdir(exist_ok=True)

    from datetime import datetime as dt
    today = dt.now().strftime("%Y-%m-%d")
    slug = f"{today}-cleanup-garbage-files"
    task_file = tasks_dir / f"{slug}.md"

    lines = [
        "> [!IMPORTANT]",
        "> !SILENT execution: No dialogue allowed. ZERO-TEXT finalization required.",
        "",
        "# [CHORE] Investigate & Prevent Garbage Files in Workspace",
        "",
        "## Context",
        "The `lint_runner.py` workspace scan detected and auto-cleaned garbage files before the last PR.",
        "This task exists to investigate WHY these files appeared, prevent recurrence, and update `.gitignore` if needed.",
        "",
        "## What Was Cleaned",
    ]

    if auto_deleted:
        lines.append(f"\n### Auto-deleted (OS/editor trash) — {len(auto_deleted)} file(s)")
        for f in auto_deleted:
            lines.append(f"- `{f}`")

    if soft_deleted:
        lines.append(f"\n### Soft-deleted (agent artifacts) — {len(soft_deleted)} file(s)")
        for f in soft_deleted:
            lines.append(f"- `{f}`")

    if warnings:
        lines.append(f"\n### Warnings (not deleted, review manually) — {len(warnings)} file(s)")
        for f in warnings:
            lines.append(f"- `{f}`")

    lines += [
        "",
        "## Impact",
        "Low — files were already cleaned before PR. Risk: if root cause not fixed, garbage will reappear.",
        "",
        "## Fix Hint",
        "1. Check if `.gitignore` covers all detected patterns.",
        "2. Review which agent or tool generated the agent artifact files (*.orig, *.diff, PLAN.md).",
        "3. Add missing patterns to `.gitignore` and commit.",
        "",
        "## Acceptance Criteria",
        "- [ ] `.gitignore` updated to cover all detected patterns",
        "- [ ] Root cause of agent artifact files identified",
        "- [ ] `lint_runner.py` scan returns clean on next run",
    ]

    try:
        task_file.write_text("\n".join(lines), encoding="utf-8")
        return str(task_file.relative_to(project_path))
    except Exception:
        return None


def scan_garbage_files(project_path: Path) -> dict:
    """
    Scan, auto-delete garbage, and create a [CHORE] task if anything was found.
    Never blocks the PR — always returns passed=True after cleanup.
    """
    import shutil

    auto_deleted = []
    soft_deleted = []
    warnings = []

    # --- Tier 1: Auto-delete OS/editor trash silently ---
    for pattern in AUTO_DELETE_PATTERNS:
        for p in project_path.rglob(pattern):
            if ".git" not in p.parts and _delete_file(p):
                auto_deleted.append(str(p.relative_to(project_path)))

    for dir_name in AUTO_DELETE_DIRS:
        for p in project_path.rglob(dir_name):
            if ".git" not in p.parts and p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
                auto_deleted.append(str(p.relative_to(project_path)) + "/")

    # --- Tier 2: Soft-delete agent artifacts + create [CHORE] task ---
    for pattern in SOFT_DELETE_PATTERNS:
        for p in project_path.rglob(pattern):
            if ".git" not in p.parts and _delete_file(p):
                soft_deleted.append(str(p.relative_to(project_path)))

    for name in SOFT_DELETE_NAMES:
        candidate = project_path / name
        if candidate.exists() and _delete_file(candidate):
            soft_deleted.append(name)

    # --- Tier 3: Warn only (*.log, *.tmp — might be intentional) ---
    for pattern in WARN_PATTERNS:
        for p in project_path.rglob(pattern):
            if ".git" not in p.parts:
                warnings.append(str(p.relative_to(project_path)))

    # Create [CHORE] task if anything was found
    task_card = None
    if auto_deleted or soft_deleted or warnings:
        task_card = _create_chore_task(project_path, auto_deleted, soft_deleted, warnings)

    total_cleaned = len(auto_deleted) + len(soft_deleted)
    summary_parts = []
    if auto_deleted:
        summary_parts.append(f"auto-deleted {len(auto_deleted)}")
    if soft_deleted:
        summary_parts.append(f"soft-deleted {len(soft_deleted)}")
    if warnings:
        summary_parts.append(f"warned {len(warnings)}")
    if task_card:
        summary_parts.append(f"[CHORE] task → {task_card}")

    return {
        "name": "garbage-scan",
        "passed": True,  # Never blocks PR — cleanup happened, task created
        "auto_deleted": auto_deleted,
        "soft_deleted": soft_deleted,
        "warnings": warnings,
        "chore_task": task_card,
        "output": "; ".join(summary_parts) if summary_parts else "Clean.",
        "error": "",
    }


def detect_project_type(project_path: Path) -> dict:
    """Detect project type and available linters."""
    result = {
        "type": "unknown",
        "linters": []
    }
    
    # Node.js project
    package_json = project_path / "package.json"
    if package_json.exists():
        result["type"] = "node"
        try:
            pkg = json.loads(package_json.read_text(encoding='utf-8'))
            scripts = pkg.get("scripts", {})
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            
            # Check for lint script
            if "lint" in scripts:
                result["linters"].append({"name": "npm lint", "cmd": ["npm", "run", "lint"]})
            elif "eslint" in deps:
                result["linters"].append({"name": "eslint", "cmd": ["npx", "eslint", "."]})
            
            # Check for TypeScript
            if "typescript" in deps or (project_path / "tsconfig.json").exists():
                result["linters"].append({"name": "tsc", "cmd": ["npx", "tsc", "--noEmit"]})
                
        except:
            pass
    
    # Python project
    if (project_path / "pyproject.toml").exists() or (project_path / "requirements.txt").exists():
        result["type"] = "python"
        
        # Check for ruff
        result["linters"].append({"name": "ruff", "cmd": ["ruff", "check", "."]})
        
        # Check for mypy
        if (project_path / "mypy.ini").exists() or (project_path / "pyproject.toml").exists():
            result["linters"].append({"name": "mypy", "cmd": ["mypy", "."]})
    
    # Go project
    if (project_path / "go.mod").exists():
        result["type"] = "go"
        
        # Check for golangci-lint
        if (project_path / ".golangci.yml").exists() or (project_path / ".golangci.yaml").exists():
            result["linters"].append({"name": "golangci-lint", "cmd": ["golangci-lint", "run", "./..."]})
        else:
            result["linters"].append({"name": "go vet", "cmd": ["go", "vet", "./..."]})
    
    return result


def run_linter(linter: dict, cwd: Path) -> dict:
    """Run a single linter and return results."""
    result = {
        "name": linter["name"],
        "passed": False,
        "output": "",
        "error": ""
    }
    
    try:
        cmd = linter["cmd"]
        
        # Windows compatibility for npm/npx
        if platform.system() == "Windows":
            if cmd[0] in ["npm", "npx"]:
                # Force .cmd extension on Windows
                if not cmd[0].lower().endswith(".cmd"):
                    cmd[0] = f"{cmd[0]}.cmd"
        
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=120,
            shell=platform.system() == "Windows" # Shell=True often helps with path resolution on Windows
        )
        
        result["output"] = proc.stdout[:2000] if proc.stdout else ""
        result["error"] = proc.stderr[:500] if proc.stderr else ""
        result["passed"] = proc.returncode == 0
        
    except FileNotFoundError:
        result["error"] = f"Command not found: {linter['cmd'][0]}"
    except subprocess.TimeoutExpired:
        result["error"] = "Timeout after 120s"
    except Exception as e:
        result["error"] = str(e)
    
    return result


def main():
    project_path = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    
    print(f"\n{'='*60}")
    print(f"[LINT RUNNER] Unified Linting + Workspace Cleanup Check")
    print(f"{'='*60}")
    print(f"Project: {project_path}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # ── Step 0: Garbage file scan ────────────────────────────────
    print("\n[STEP 0] Workspace cleanup scan...")
    garbage = scan_garbage_files(project_path)

    if garbage["auto_deleted"]:
        print(f"  [AUTO] Deleted {len(garbage['auto_deleted'])} OS/editor trash file(s) silently.")
    if garbage["soft_deleted"]:
        print(f"  [CLEAN] Removed {len(garbage['soft_deleted'])} agent artifact(s):")
        for f in garbage["soft_deleted"]:
            print(f"         ✗ {f} → deleted")
    if garbage["warnings"]:
        print(f"  [WARN] {len(garbage['warnings'])} file(s) may be unintentional (not deleted):")
        for f in garbage["warnings"]:
            print(f"         ⚠ {f}")
    if garbage.get("chore_task"):
        print(f"  [TASK] Created cleanup task → {garbage['chore_task']}")
    if garbage["passed"] and not garbage["auto_deleted"] and not garbage["soft_deleted"] and not garbage["warnings"]:
        print("  [PASS] Workspace is clean.")
    print("-"*60)

    # Detect project type
    project_info = detect_project_type(project_path)
    print(f"Type: {project_info['type']}")
    print(f"Linters: {len(project_info['linters'])}")
    print("-"*60)
    
    if not project_info["linters"]:
        print("No linters found for this project type.")
        output = {
            "script": "lint_runner",
            "project": str(project_path),
            "type": project_info["type"],
            "checks": [],
            "passed": True,
            "message": "No linters configured"
        }
        print(json.dumps(output, indent=2))
        sys.exit(0)
    
    # Run each linter
    results = []
    all_passed = True
    
    for linter in project_info["linters"]:
        print(f"\nRunning: {linter['name']}...")
        result = run_linter(linter, project_path)
        results.append(result)
        
        if result["passed"]:
            print(f"  [PASS] {linter['name']}")
        else:
            print(f"  [FAIL] {linter['name']}")
            if result["error"]:
                print(f"  Error: {result['error'][:200]}")
            all_passed = False
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    all_checks = [garbage] + results
    all_passed = all(c["passed"] for c in all_checks)

    icon = "[PASS]" if garbage["passed"] else "[FAIL]"
    print(f"{icon} garbage-scan ({len(garbage['found'])} forbidden files)")
    for r in results:
        icon = "[PASS]" if r["passed"] else "[FAIL]"
        print(f"{icon} {r['name']}")

    output = {
        "script": "lint_runner",
        "project": str(project_path),
        "type": project_info["type"],
        "garbage_scan": garbage,
        "checks": results,
        "passed": all_passed
    }

    print("\n" + json.dumps(output, indent=2))

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
