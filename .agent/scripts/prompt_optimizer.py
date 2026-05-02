#!/usr/bin/env python3
"""Prompt Optimizer — Analyzes telemetry to suggest token and cost reductions.
"""
import sys
import json
from pathlib import Path
from collections import defaultdict

try:
    from lib.paths import BUS_DIR
    from lib.common import load_json_safe
except ImportError:
    sys.path.append(str(Path(__file__).resolve().parent))
    from lib.paths import BUS_DIR
    from lib.common import load_json_safe

def analyze_telemetry():
    bus_file = BUS_DIR / "context.json"
    if not bus_file.exists():
        return "No telemetry data found on the bus."

    data = load_json_safe(bus_file)
    objects = data.get("objects", [])
    
    agent_stats = defaultdict(lambda: {"tokens": 0, "calls": 0})
    
    for obj in objects:
        if obj.get("type") == "telemetry":
            content = obj.get("content", {})
            author = obj.get("author", "unknown")
            tokens = content.get("total_tokens", 0)
            agent_stats[author]["tokens"] += tokens
            agent_stats[author]["calls"] += 1

    if not agent_stats:
        return "No telemetry entries found."

    report = ["\n💰 PROMPT COST OPTIMIZATION REPORT"]
    for agent, stats in agent_stats.items():
        avg = stats["tokens"] / stats["calls"]
        report.append(f"\n🤖 Agent: {agent}")
        report.append(f"   - Total Tokens: {stats['tokens']}")
        report.append(f"   - Average per call: {avg:.1f}")
        
        if avg > 50000:
            report.append("   ⚠️  HIGH USAGE: Consider trimming system prompt or reducing context depth.")
        elif avg > 20000:
            report.append("   💡 TIP: Check for redundant greetings or duplicate instructions.")
        else:
            report.append("   ✅ EFFICIENT: Prompt size is within optimal range.")

    return "\n".join(report)

if __name__ == "__main__":
    print(analyze_telemetry())
