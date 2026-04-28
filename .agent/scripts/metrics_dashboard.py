#!/usr/bin/env python3
import json
import os
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich import box

REPO_ROOT = Path(__file__).parent.parent.parent
METRICS_FILE = REPO_ROOT / ".agent" / "logs" / "metrics.jsonl"
console = Console()

def load_metrics():
    if not METRICS_FILE.exists():
        return []
    metrics = []
    with open(METRICS_FILE, "r") as f:
        for line in f:
            try:
                metrics.append(json.loads(line))
            except:
                pass
    return metrics

def generate_dashboard():
    metrics = load_metrics()
    
    # Summary stats
    total_events = len(metrics)
    agents = set(m.get("agent") for m in metrics)
    
    table = Table(title="🚀 Universal Live Metrics", box=box.ROUNDED, expand=True)
    table.add_column("Timestamp", style="cyan")
    table.add_column("Agent", style="magenta")
    table.add_column("Metric", style="yellow")
    table.add_column("Value", style="green")
    table.add_column("Status", style="bold")

    # Show last 10 events
    for m in metrics[-10:]:
        ts = m.get("ts", "").split("T")[-1][:8]
        status = m.get("status", "N/A")
        status_style = "green" if status == "success" else "red" if status == "error" else "white"
        
        table.add_row(
            ts,
            m.get("agent", "unknown"),
            m.get("metric", "N/A"),
            str(m.get("value", "N/A")),
            f"[{status_style}]{status}[/]"
        )

    return table

def main():
    if not METRICS_FILE.exists():
        console.print("[red]No metrics found. Waiting for agent activity...[/]")
        return

    with Live(generate_dashboard(), refresh_per_second=1) as live:
        try:
            while True:
                live.update(generate_dashboard())
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            pass

if __name__ == "__main__":
    main()
