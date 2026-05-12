import json
import os
import sys
import uuid
from datetime import datetime, timezone
import argparse

LOG_PATH = ".agent/logs/metrics.jsonl"

def log_event(agent, metric, value, metadata=None):
    """
    Logs a metric event to the local metrics file.
    """
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event_id": str(uuid.uuid4()),
        "agent": agent,
        "metric": metric,
        "value": value,
        "session_id": os.environ.get("CONVERSATION_ID", "local"),
        "metadata": metadata or {}
    }
    
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")
    
    return event

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Log agent metrics.")
    parser.add_argument("--agent", required=True, help="Agent name")
    parser.add_argument("--metric", required=True, help="Metric type (latency_ms, tokens, etc.)")
    parser.add_argument("--value", required=True, help="Metric value")
    parser.add_argument("--meta", help="JSON metadata string")
    
    args = parser.parse_args()
    
    metadata = {}
    if args.meta:
        try:
            metadata = json.loads(args.meta)
        except json.JSONDecodeError:
            print(f"Error decoding metadata JSON: {args.meta}", file=sys.stderr)
    
    # Try to convert value to number if possible
    try:
        if "." in args.value:
            value = float(args.value)
        else:
            value = int(args.value)
    except ValueError:
        value = args.value
        
    result = log_event(args.agent, args.metric, value, metadata)
    print(json.dumps(result, indent=2))
