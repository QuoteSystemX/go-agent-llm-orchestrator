import os
import json
import re

BUS_DIR = ".agent/bus/outputs"
def find_app_data_path(filename):
    # Try environment variable first
    env_path = os.environ.get("AGENT_APP_DATA_DIR")
    if env_path:
        path = os.path.join(env_path, "brain", "b6e6196a-8f3d-49cf-b328-148123206a3c", filename)
        if os.path.exists(path):
            return path

    # Common base paths for Antigravity and Cloud Core
    bases = [
        os.path.expanduser("~/.gemini/antigravity"),
        os.path.expanduser("~/.anthropic/anthropic-code"),
        os.path.expanduser("~/.cloud-core")
    ]
    
    for base in bases:
        path = os.path.join(base, "brain", "b6e6196a-8f3d-49cf-b328-148123206a3c", filename)
        if os.path.exists(path):
            return path
            
    return None

TASK_PATH = find_app_data_path("task_output_gateway.md")

def get_latest_goal():
    outputs = []
    if not os.path.exists(BUS_DIR):
        return None
    
    files = sorted(os.listdir(BUS_DIR), reverse=True)
    if not files:
        return None
        
    with open(os.path.join(BUS_DIR, files[0]), "r") as f:
        return json.load(f).get("goal", "").lower()

def sync_tasks():
    latest_goal = get_latest_goal()
    if not latest_goal:
        return

    if not os.path.exists(TASK_PATH):
        return

    with open(TASK_PATH, "r") as f:
        lines = f.readlines()

    updated = False
    new_lines = []
    for line in lines:
        # Check if line is an uncompleted task
        match = re.match(r"(\s*)- \[ \]\s*(.*)", line)
        if match:
            indent, task_text = match.groups()
            # Simple fuzzy match: if latest goal contains keywords from task text
            # This is a bit naive but works for demonstration
            keywords = re.findall(r"\w+", task_text.lower())
            if any(k in latest_goal for k in keywords if len(k) > 3):
                new_lines.append(f"{indent}- [x] {task_text}\n")
                updated = True
                continue
        new_lines.append(line)

    if updated:
        with open(TASK_PATH, "w") as f:
            f.writelines(new_lines)
        print(f"✅ Tasks synced in {TASK_PATH}")

if __name__ == "__main__":
    sync_tasks()
