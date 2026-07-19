#!/usr/bin/env python3
"""
Unified Sync and Compilation Pipeline — Antigravity Kit
======================================================
Consolidates all compilation, client distribution, parity checks,
and code debt collection into a single high-performance pipeline.
"""

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

import sys
import subprocess
from pathlib import Path

# Try importing common REPO_ROOT
try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]

# ANSI colors for status logging
class Colors:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def log_header(text: str):
    print(f"\n{Colors.BOLD}{Colors.CYAN}╓{'─'*58}╖{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}║ {text.center(56)} ║{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}╙{'─'*58}╜{Colors.ENDC}\n")

def log_step(text: str):
    print(f"{Colors.BOLD}{Colors.CYAN}🔄 {text}...{Colors.ENDC}")

def log_success(text: str):
    print(f"{Colors.GREEN}✅ {text}{Colors.ENDC}")

def log_warning(text: str):
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.ENDC}")

def log_error(text: str):
    print(f"{Colors.RED}❌ {text}{Colors.ENDC}")

def run_script(name: str, path: Path, args: list = None) -> bool:
    if args is None:
        args = []
    log_step(f"Running {name}")
    
    if not path.exists():
        log_error(f"Script {name} not found at {path}")
        return False
        
    try:
        cmd = [sys.executable, str(path)] + args
        result = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            log_success(f"{name} completed successfully.")
            if result.stdout.strip():
                # Print output indented
                for line in result.stdout.strip().splitlines():
                    print(f"   {line}")
            return True
        else:
            log_error(f"{name} failed with exit code {result.returncode}!")
            if result.stdout:
                print(f"Stdout:\n{result.stdout}")
            if result.stderr:
                print(f"Stderr:\n{result.stderr}")
            return False
    except Exception as e:
        log_error(f"Execution of {name} raised exception: {e}")
        return False

def main() -> None:
    log_header("ANTIGRAVITY UNIFIED SYNC PIPELINE")
    
    scripts_root = REPO_ROOT / ".agent" / "scripts"
    
    pipeline = [
        ("Modular Rules Compilation", scripts_root / "dev" / "compile_rules.py", []),
        ("MCP Config Provisioning", scripts_root / "delivery" / "mcp_config_setup.py", []),
        ("Claude Target Agent Parity Sync", scripts_root / "delivery" / "sync_agents.py", ["--target", "claude"]),
        ("OpenCode Target Agent Parity Sync", scripts_root / "delivery" / "sync_agents.py", ["--target", "opencode"]),
        ("Parity Metric Verification", scripts_root / "delivery" / "sync_parity_collector.py", []),
        ("Linter Debt Collection", scripts_root / "dev" / "linter_debt_collector.py", []),
        ("Workspace Status Dashboard Update", scripts_root / "health" / "status_report.py", ["--html"]),
    ]
    
    overall_success = True
    for name, path, args in pipeline:
        success = run_script(name, path, args)
        if not success:
            overall_success = False
            
    print()
    if overall_success:
        log_success("ALL PIPELINE SYNCS COMPLETED SUCCESSFULLY!")
        sys.exit(0)
    else:
        log_warning("PIPELINE COMPLETED WITH SOME WARNINGS OR ERRORS.")
        sys.exit(1)

if __name__ == "__main__":
    main()
