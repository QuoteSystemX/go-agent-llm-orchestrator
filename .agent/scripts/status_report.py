#!/usr/bin/env python3
import os
import subprocess
import json
from pathlib import Path
from datetime import datetime

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich import box
except ImportError:
    class Console:
        def print(self, msg, **kwargs):
            if hasattr(msg, "content"):
                print(f"\n--- {msg.title} ---\n{msg.content}\n")
            elif hasattr(msg, "__str__") and not isinstance(msg, (str, int, float)):
                print(str(msg))
            else:
                print(msg)
    class Panel:
        def __init__(self, content, title="", **kwargs):
            self.content = content
            self.title = title
    class Table:
        def __init__(self, **kwargs):
            self.rows = []
            self.cols = []
        def add_column(self, name, **kwargs): self.cols.append(name)
        def add_row(self, *args): self.rows.append(args)
        def __str__(self):
            res = " | ".join(self.cols) + "\n" + "-"*40 + "\n"
            for r in self.rows:
                res += " | ".join(map(str, r)) + "\n"
            return res
        def __rich__(self): return str(self)
    box = None

REPO_ROOT = Path(__file__).parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / ".agent" / "scripts"
LINT_SCRIPTS_DIR = REPO_ROOT / ".agent" / "skills" / "lint-and-validate" / "scripts"

def run_script(cmd, cwd=REPO_ROOT):
    try:
        res = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, encoding='utf-8')
        return res.stdout, res.stderr, res.returncode
    except Exception as e:
        return "", str(e), 1

def get_lint_status():
    lint_runner = LINT_SCRIPTS_DIR / "lint_runner.py"
    if not lint_runner.exists():
        return "Not found", False
    stdout, stderr, code = run_script(["python3", str(lint_runner), "."])
    try:
        json_str = stdout.strip().split("\n\n")[-1]
        data = json.loads(json_str)
        return data, data.get("passed", False)
    except:
        return stdout, code == 0

def main():
    console = Console()
    console.print(Panel("[bold cyan]🚀 Repository Status Report[/bold cyan]", title="Antigravity Kit Dashboard", box=box.DOUBLE if box else None))
    
    # 1. Workspace Health
    console.print("\n[bold]🧪 Technical Health (lint_runner)[/bold]")
    lint_data, lint_passed = get_lint_status()
    if isinstance(lint_data, dict):
        table = Table(box=box.SIMPLE if box else None)
        table.add_column("Check", style="cyan")
        table.add_column("Status", justify="center")
        table.add_column("Detail", style="dim")
        for key in ["garbage_scan", "drift_check", "commit_lint", "type_coverage"]:
            g = lint_data.get(key, {})
            table.add_row(key.replace("_", " ").title(), "[green]PASS[/]" if g.get("passed") else "[red]FAIL[/]", g.get("output", ""))
        console.print(table)
    else:
        console.print(f"[red]Error parsing lint results.[/red]")

    # 2. Business Dashboard
    console.print("\n[bold]📈 Business Progress[/bold]")
    biz_script = SCRIPTS_DIR / "business_dashboard.py"
    if biz_script.exists():
        stdout, stderr, _ = run_script(["python3", str(biz_script)])
        console.print(stdout)

    # 3. Experience Distillation
    console.print("\n[bold]🧹 Experience Distillation[/bold]")
    distiller_script = SCRIPTS_DIR / "experience_distiller.py"
    if distiller_script.exists():
        stdout, stderr, _ = run_script(["python3", str(distiller_script)])
        console.print(stdout.strip())
    
    # 4. Git Hooks Status
    console.print("\n[bold]🪝 Git Hooks[/bold]")
    hook_path = REPO_ROOT / ".git" / "hooks" / "pre-commit"
    if hook_path.exists():
        console.print("[green]✅ Pre-commit hygiene hook is installed.[/green]")
    else:
        console.print("[yellow]⚠️  Pre-commit hook NOT installed. Run 'python3 .agent/scripts/install_hooks.py' to enable.[/yellow]")

    # 5. Recent Telemetry
    console.print("\n[bold]📡 Recent Agent Activity[/bold]")
    metrics_script = SCRIPTS_DIR / "metrics_dashboard.py"
    if metrics_script.exists():
        env = os.environ.copy()
        env["NON_INTERACTIVE"] = "1"
        try:
            res = subprocess.run(["python3", str(metrics_script)], cwd=str(REPO_ROOT), capture_output=True, text=True, env=env)
            console.print(res.stdout)
        except:
            console.print("[red]Error running metrics dashboard.[/red]")

    console.print("\n" + "="*60)
    final_status = "[green]HEALTHY[/]" if lint_passed else "[red]DEGRADED[/]"
    console.print(f"Final Integrity Status: {final_status}")
    console.print("="*60)

if __name__ == "__main__":
    main()
