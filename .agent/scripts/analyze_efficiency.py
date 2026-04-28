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
                agent = m.get("agent", "unknown")
                metric = m.get("metric")
                val = m.get("value")
                status = m.get("status")
                
                # Track tokens
                if metric in ["prompt_tokens", "completion_tokens"]:
                    stats[agent]["tokens"] += int(val)
                
                # Track latency
                if metric == "latency_ms":
                    stats[agent]["latency"].append(int(val))
                
                # Track status (from field or from metric 'status')
                if status == "success" or (metric == "status" and val == "success"):
                    stats[agent]["success"] += 1
                elif status == "error" or (metric == "status" and val == "error"):
                    stats[agent]["error"] += 1
            except:
                pass

    print("# AI Efficiency Analysis Report\n")
    if not stats:
        print("No valid events found in log.")
        return

    for agent, s in sorted(stats.items()):
        avg_lat = sum(s["latency"]) / len(s["latency"]) if s["latency"] else 0
        total = s["success"] + s["error"]
        success_rate = (s["success"] / total * 100) if total > 0 else 100.0 # Default to 100 if no status recorded
        
        print(f"## Agent: `{agent}`")
        print(f"- **Total Tokens**: {s['tokens']:,}")
        print(f"- **Avg Latency**: {avg_lat:.0f}ms")
        print(f"- **Success Rate**: {success_rate:.1f}%")
        
        # Recommendations
        recs = []
        if total > 0 and success_rate < 90:
            recs.append("⚠️ High error rate. Review system prompt or context.")
        if s["tokens"] > 50000:
            recs.append("⚠️ High token usage. Use Context Bus to offload data.")
        if avg_lat > 10000:
            recs.append("🐢 High latency. Consider using a faster model (Haiku).")
            
        if recs:
            for r in recs:
                print(f"- {r}")
        else:
            print("- ✅ Performance is within optimal parameters.")
        print()

if __name__ == "__main__":
    analyze()
