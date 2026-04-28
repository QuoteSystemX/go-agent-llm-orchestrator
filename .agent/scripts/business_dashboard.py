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
except ImportError:
    print("Error: 'rich' library required. Run 'pip install rich'.")
    exit(1)

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
    console.print(f"\n[bold]Total Velocity:[/] [green]{sum(f['completed'] for f in features.values())}[/] / {sum(f['total'] for f in features.values())} Story Cards")

if __name__ == "__main__":
    show_dashboard()
