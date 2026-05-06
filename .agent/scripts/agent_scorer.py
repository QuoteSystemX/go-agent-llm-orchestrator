#!/usr/bin/env python3
import json
import os
import sys
from datetime import datetime
from pathlib import Path

DATA_FILE = Path(__file__).parent.parent / "data" / "pr-quality.jsonl"

def log_score(agent_name, task_id, score, comments=""):
    """Log a quality score for an agent's work."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "agent": agent_name,
        "task_id": task_id,
        "score": score,
        "comments": comments
    }
    
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    
    print(f"✅ Logged score {score} for @{agent_name} on task {task_id}")

def get_stats(agent_name=None):
    """Calculate average scores."""
    if not DATA_FILE.exists():
        return {}
    
    scores = {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                data = json.loads(line)
                name = data["agent"]
                if agent_name and name != agent_name:
                    continue
                if name not in scores:
                    scores[name] = []
                scores[name].append(data["score"])
            except:
                continue
    
    stats = {}
    for name, s_list in scores.items():
        stats[name] = {
            "avg": sum(s_list) / len(s_list),
            "count": len(s_list)
        }
    return stats

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python agent_scorer.py log <agent> <task_id> <score> [comments]")
        print("       python agent_scorer.py stats [agent]")
        sys.exit(1)
        
    cmd = sys.argv[1]
    if cmd == "log":
        agent = sys.argv[2]
        task = sys.argv[3]
        score = float(sys.argv[4])
        comments = sys.argv[5] if len(sys.argv) > 5 else ""
        log_score(agent, task, score, comments)
    elif cmd == "stats":
        agent = sys.argv[2] if len(sys.argv) > 2 else None
        stats = get_stats(agent)
        print(json.dumps(stats, indent=2))
