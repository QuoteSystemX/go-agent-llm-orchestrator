#!/usr/bin/env python3
import os
import re
from pathlib import Path

try:
    from rich.console import Console
    from rich.table import Table
    from rich.progress import ProgressBar
    from rich.panel import Panel
    from rich import box
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    class Console:
        def print(self, msg, **kwargs): print(msg)

REPO_ROOT = Path(__file__).parent.parent.parent
TASKS_DIR = REPO_ROOT / "tasks"

def parse_tasks():
    features = {} # {feature_name: [total, completed]}
    sprints = {"active": 0, "total": 0, "completed": 0}
    
    if not TASKS_DIR.exists():
        return None, None
        
    for f in TASKS_DIR.glob("*.md"):
        content = f.read_text()
        
        # Determine feature (from Context or Epic metadata in card)
        feature = "General"
        match = re.search(r"Epic:\s*(.*)", content)
        if match:
            feature = match.group(1).strip()
        
        # Check completion
        is_completed = "[x]" in content.lower()
        
        if feature not in features:
            features[feature] = {"total": 0, "completed": 0}
            
        features[feature]["total"] += 1
        if is_completed:
            features[feature]["completed"] += 1
            
    return features, sprints

def show_dashboard():
    console = Console()
    features, sprints = parse_tasks()
    
    if not features:
        console.print("[yellow]No tasks found in tasks/ directory.[/yellow]")
        return

    total_tasks = sum(f['total'] for f in features.values())
    completed_tasks = sum(f['completed'] for f in features.values())
    overall_percent = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0

    if not HAS_RICH:
        console.print("=== Business Progress Dashboard ===")
        for feat, stats in features.items():
            total = stats["total"]
            done = stats["completed"]
            percent = (done / total * 100) if total > 0 else 0
            console.print(f"{feat}: {percent:.1f}% ({done}/{total} Tasks)")
        console.print(f"\nOverall Progress: {overall_percent:.1f}%")
        console.print(f"Velocity: {completed_tasks} / {total_tasks} Story Cards")
        return

    table = Table(title="📈 Business Progress Dashboard", box=box.DOUBLE_EDGE, expand=True)
    table.add_column("Feature Area", style="cyan", no_wrap=True)
    table.add_column("Progress", style="magenta")
    table.add_column("Status", justify="right")

    for feat, stats in features.items():
        total = stats["total"]
        done = stats["completed"]
        percent = (done / total * 100) if total > 0 else 0
        
        # Simple progress bar string
        bar_width = 20
        filled = int(percent / 100 * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)
        
        color = "green" if percent == 100 else "yellow" if percent > 0 else "red"
        
        table.add_row(
            feat,
            f"[{color}]{bar}[/] {percent:.1f}%",
            f"{done}/{total} Tasks"
        )

    console.print(table)
    
    # Velocity & Forecast
    console.print(Panel(
        f"[bold]Total Progress:[/] [green]{overall_percent:.1f}%[/]\n"
        f"[bold]Velocity:[/] {completed_tasks} / {total_tasks} Tasks\n"
        f"[bold]Estimated Remaining:[/] {total_tasks - completed_tasks} Tasks",
        title="🏁 Velocity & Forecast",
        box=box.ROUNDED
    ))

if __name__ == "__main__":
    show_dashboard()
