#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from collections import defaultdict

REPO_ROOT = Path(__file__).parent.parent.parent
METRICS_FILE = REPO_ROOT / ".agent" / "logs" / "metrics.jsonl"

def analyze():
    if not METRICS_FILE.exists():
        print("No metrics to analyze.")
        return

    stats = defaultdict(lambda: {"tokens": 0, "latency": [], "success": 0, "error": 0})
    
    with open(METRICS_FILE, "r") as f:
        for line in f:
            try:
                m = json.loads(line)
                agent = m.get("agent")
                metric = m.get("metric")
                val = m.get("value")
                
                if metric == "prompt_tokens" or metric == "completion_tokens":
                    stats[agent]["tokens"] += int(val)
                elif metric == "latency_ms":
                    stats[agent]["latency"].append(int(val))
                elif metric == "status":
                    if val == "success": stats[agent]["success"] += 1
                    else: stats[agent]["error"] += 1
            except:
                pass

    print("# AI Efficiency Analysis Report\n")
    for agent, s in stats.items():
        avg_lat = sum(s["latency"]) / len(s["latency"]) if s["latency"] else 0
        total = s["success"] + s["error"]
        success_rate = (s["success"] / total * 100) if total > 0 else 0
        
        print(f"## Agent: `{agent}`")
        print(f"- **Total Tokens**: {s['tokens']}")
        print(f"- **Avg Latency**: {avg_lat:.0f}ms")
        print(f"- **Success Rate**: {success_rate:.1f}%")
        
        # Simple AI-like recommendations
        if success_rate < 80:
            print("- ⚠️ [RECOMMENDATION] High error rate. Consider reviewing the systemic prompt or splitting the task.")
        if s["tokens"] > 50000:
            print("- ⚠️ [RECOMMENDATION] High token usage. Suggest using the Context Bus to reduce context size.")
        print()

if __name__ == "__main__":
    analyze()
