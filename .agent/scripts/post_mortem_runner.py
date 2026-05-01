#!/usr/bin/env python3
"""Post-Mortem Runner — Analyzes failure logs and suggests lessons learned.
"""
import sys
import os
from pathlib import Path
from datetime import datetime

try:
    from lib.paths import AGENT_DIR, LESSONS_PATH
    from lib.common import load_json_safe
except ImportError:
    sys.path.append(str(Path(__file__).resolve().parent))
    from lib.paths import AGENT_DIR, LESSONS_PATH
    from lib.common import load_json_safe

LOG_DIR = AGENT_DIR / "logs"

def analyze_recent_failures():
    """Scan log directory for recent errors and extract context."""
    if not LOG_DIR.exists():
        return "No logs found to analyze."

    logs = sorted(LOG_DIR.glob("*.log"), key=os.path.getmtime, reverse=True)
    if not logs:
        return "No recent logs found."

    recent_log = logs[0]
    with open(recent_log, "r", encoding="utf-8") as f:
        content = f.read()

    # Heuristic for finding error context
    lines = content.splitlines()
    error_lines = [l for l in lines if "ERROR" in l or "Exception" in l or "Failed" in l]
    
    if not error_lines:
        return f"No obvious errors found in {recent_log.name}."

    date_str = datetime.now().strftime("%Y-%m-%d")
    
    suggestion = f"""### [{date_str}] [FAIL] [skill-name] Title of the issue
Context: Analysis of {recent_log.name} detected:
{error_lines[-1] if error_lines else "Unknown error"}

Root Cause: [Describe why it failed]
Resolution: [How was it fixed?]
"""
    return f"Suggested lesson learned based on {recent_log.name}:\n\n{suggestion}"

def main():
    print(analyze_recent_failures())

if __name__ == "__main__":
    main()
