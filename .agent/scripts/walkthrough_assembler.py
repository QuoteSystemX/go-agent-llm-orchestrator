import os
import json
import re
from datetime import datetime

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
        os.path.expanduser("~/.anthropic/anthropic-code"), # Potential Cloud Core path
        os.path.expanduser("~/.cloud-core") # Alternative
    ]
    
    for base in bases:
        path = os.path.join(base, "brain", "b6e6196a-8f3d-49cf-b328-148123206a3c", filename)
        if os.path.exists(path):
            return path
            
    return None

WALKTHROUGH_PATH = find_app_data_path("walkthrough.md")

def get_session_outputs():
    outputs = []
    if not os.path.exists(BUS_DIR):
        return []
    
    for filename in sorted(os.listdir(BUS_DIR)):
        if filename.endswith(".json"):
            with open(os.path.join(BUS_DIR, filename), "r") as f:
                outputs.append(json.load(f))
    return outputs

def format_entry(output):
    timestamp = output.get("timestamp", "unknown")
    agent = output.get("agent", "unknown")
    goal = output.get("goal", "No goal provided")
    files = output.get("impacted_files", [])
    
    entry = f"\n### [{timestamp}] {agent}\n"
    entry += f"- **Goal**: {goal}\n"
    if files:
        entry += "- **Files**:\n"
        for f in files:
            entry += f"  - `{f}`\n"
    return entry

def update_walkthrough():
    outputs = get_session_outputs()
    if not outputs:
        print("No outputs found in Bus.")
        return

    if not os.path.exists(WALKTHROUGH_PATH):
        print(f"Walkthrough file not found at {WALKTHROUGH_PATH}")
        return

    with open(WALKTHROUGH_PATH, "r") as f:
        content = f.read()

    # Check if we already have a Session Log section
    log_section_header = "## 📝 Session Activity Log"
    if log_section_header not in content:
        content += f"\n\n{log_section_header}\n"

    # For simplicity, we just rebuild the log section from all outputs in this session
    log_entries = ""
    for out in outputs:
        log_entries += format_entry(out)

    # Replace old log with new one
    new_content = re.sub(f"{log_section_header}.*", f"{log_section_header}\n{log_entries}", content, flags=re.DOTALL)

    with open(WALKTHROUGH_PATH, "w") as f:
        f.write(new_content)
    
    print(f"✅ Walkthrough updated at {WALKTHROUGH_PATH}")

if __name__ == "__main__":
    update_walkthrough()
