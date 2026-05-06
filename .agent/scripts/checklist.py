#!/usr/bin/env python3
"""
Master Checklist Runner - Antigravity Kit
==========================================

Orchestrates all validation scripts in priority order.
Supports --fix for auto-correcting common issues.
"""

import sys
import subprocess
import argparse
from pathlib import Path
from typing import List, Tuple, Optional

# Import from common lib
try:
    from lib.paths import WATCHDOG_RULES_PATH, CONFIG_DIR, RULES_DIR, REPO_ROOT
    from lib.common import load_json_safe, validate_json
except ImportError:
    sys.path.append(str(Path(__file__).resolve().parent))
    from lib.paths import WATCHDOG_RULES_PATH, CONFIG_DIR, RULES_DIR, REPO_ROOT
    from lib.common import load_json_safe, validate_json

# ANSI colors
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(text: str):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text.center(60)}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.ENDC}\n")

def print_step(text: str):
    print(f"{Colors.BOLD}{Colors.BLUE}🔄 {text}{Colors.ENDC}")

def print_success(text: str):
    print(f"{Colors.GREEN}✅ {text}{Colors.ENDC}")

def print_warning(text: str):
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.ENDC}")

def print_error(text: str):
    print(f"{Colors.RED}❌ {text}{Colors.ENDC}")

# Define priority-ordered checks
CORE_CHECKS = [
    ("Security Scan", ".agent/skills/vulnerability-scanner/scripts/security_scan.py", True),
    ("Lint Check", ".agent/skills/lint-and-validate/scripts/lint_runner.py", True),
    ("Schema Validation", ".agent/skills/database-design/scripts/schema_validator.py", False),
    ("Test Runner", ".agent/skills/testing-patterns/scripts/test_runner.py", False),
    ("UX Audit", ".agent/skills/frontend-design/scripts/ux_audit.py", False),
    ("SEO Check", ".agent/skills/seo-fundamentals/scripts/seo_checker.py", False),
]

def check_watchdog_schema() -> tuple[bool, str]:
    """Validate watchdog_rules.json against its schema."""
    schema_path = CONFIG_DIR / "watchdog_schema.json"
    if not WATCHDOG_RULES_PATH.exists():
        return True, "No watchdog rules found, skipping."
    
    rules = load_json_safe(WATCHDOG_RULES_PATH)
    return validate_json(rules, schema_path)

def run_fix():
    """Attempt to fix common issues."""
    print_header("🛠 AUTO-FIXING ISSUES")
    
    # 1. Ensure core directories exist
    from lib.paths import BUS_DIR, CONFIG_DIR, RULES_DIR, AGENT_DIR, SCRIPTS_DIR
    dirs = [
        AGENT_DIR, 
        BUS_DIR, 
        CONFIG_DIR, 
        RULES_DIR, 
        SCRIPTS_DIR,
        REPO_ROOT / ".agent/logs",
        REPO_ROOT / "wiki/archive/experience",
        REPO_ROOT / "tasks"
    ]
    for d in dirs:
        if not d.exists():
            print_step(f"Creating directory: {d}")
            d.mkdir(parents=True, exist_ok=True)
            print_success(f"Created {d}")

    # 2. Fix permissions for scripts
    print_step("Ensuring scripts are executable...")
    for script in SCRIPTS_DIR.glob("**/*.py"):
        try:
            current_mode = script.stat().st_mode
            script.chmod(current_mode | 0o111)
        except Exception as e:
            print_warning(f"Failed to set permissions for {script}: {e}")
    print_success("Script permissions checked.")

    # 3. Basic watchdog rules if missing or broken
    rules_valid = False
    if WATCHDOG_RULES_PATH.exists():
        rules = load_json_safe(WATCHDOG_RULES_PATH)
        if rules and "limits" in rules and "dangerous_operations" in rules:
            rules_valid = True
        else:
            print_warning("watchdog_rules.json is invalid or incomplete. Healing...")

    if not WATCHDOG_RULES_PATH.exists() or not rules_valid:
        print_step("Restoring default watchdog_rules.json")
        default_rules = {
            "limits": {
                "token_budget_per_task": 200000,
                "cost_limit_per_task_usd": 5.0
            },
            "dangerous_operations": {
                "commands": {
                    "block": ["rm -rf /", "mkfs", "dd if="],
                    "warn": ["rm -rf", "chmod -R 777"]
                },
                "files": {
                    "protected": [".env*", "id_rsa*", "*.pem"]
                }
            }
        }
        import json
        with open(WATCHDOG_RULES_PATH, 'w', encoding="utf-8") as f:
            json.dump(default_rules, f, indent=2)
        print_success("Healed watchdog rules.")
    
    # 4. Auto-update Visualization and Dashboard
    print_step("Updating Visualization and Dashboard...")
    try:
        import visualize_deps
        import status_report
        import task_tracer
        import prompt_optimizer
        
        # Trace check: warning if changes exist but no task is active
        staged = task_tracer.get_staged_files()
        if staged and not task_tracer.find_active_task():
            print_warning("Changes detected but no active task found in tasks/.")
            
        visualize_deps.generate_mermaid()
        score, metrics = status_report.calculate_health()
        
        # Add cost metrics to dashboard (simplified for demo)
        opt_report = prompt_optimizer.analyze_telemetry()
        if "HIGH USAGE" in opt_report:
            score -= 10
            metrics["Cost Status"] = "⚠️ HIGH"
        else:
            metrics["Cost Status"] = "✅ OK"
            
        status_report.export_to_html(score, metrics)
        
        # Doc Healer: Auto-repair documentation drift
        import doc_healer
        doc_healer.heal_docs()
        
        print_success("Visualization, Dashboard, and Documentation updated.")
    except Exception as e:
        print_warning(f"Failed to update visualization: {e}")

    print_success("Auto-fix complete.")

def main():
    parser = argparse.ArgumentParser(description="Run Antigravity Kit validation checklist")
    parser.add_argument("project", help="Project path to validate")
    parser.add_argument("--fix", action="store_true", help="Attempt to fix simple issues")
    parser.add_argument("--url", help="URL for performance checks")
    
    args = parser.parse_args()
    
    if args.fix:
        run_fix()

    print_header("🚀 ANTIGRAVITY KIT - MASTER CHECKLIST")
    
    results = []
    
    # Custom Check: Watchdog Schema
    print_step("Checking Watchdog Rules Schema")
    ok, msg = check_watchdog_schema()
    if ok:
        print_success(f"Watchdog Schema: {msg}")
        results.append({"name": "Watchdog Schema", "passed": True})
    else:
        print_error(f"Watchdog Schema: {msg}")
        results.append({"name": "Watchdog Schema", "passed": False})

    # Core checks execution
    print_header("📋 CORE CHECKS")
    
    overall_passed = True
    for name, script_path, mandatory in CORE_CHECKS:
        full_path = REPO_ROOT / script_path
        if not full_path.exists():
            print_warning(f"Skipping {name}: Script {script_path} not found.")
            continue
            
        print_step(f"Running {name}...")
        try:
            # Run the script and capture output
            result = subprocess.run(
                [sys.executable, str(full_path)],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                print_success(f"{name} passed.")
                results.append({"name": name, "passed": True})
            else:
                if mandatory:
                    print_error(f"{name} failed!")
                    print(result.stdout)
                    print(result.stderr)
                    overall_passed = False
                else:
                    print_warning(f"{name} failed (non-blocking).")
                results.append({"name": name, "passed": False})
                
        except Exception as e:
            print_error(f"Error running {name}: {e}")
            if mandatory:
                overall_passed = False
            results.append({"name": name, "passed": False})

    print_header("🏁 FINAL STATUS")
    for res in results:
        status = f"{Colors.GREEN}PASS{Colors.ENDC}" if res["passed"] else f"{Colors.RED}FAIL{Colors.ENDC}"
        print(f"| {res['name']:<25} | {status} |")
    
    if not overall_passed:
        print_error("\nChecklist FAILED. Please fix the mandatory issues above.")
        sys.exit(1)
    else:
        print_success("\nAll core checks passed! Ready to proceed.")

if __name__ == "__main__":
    main()
