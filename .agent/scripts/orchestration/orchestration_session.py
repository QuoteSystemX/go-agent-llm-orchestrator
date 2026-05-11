
# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    import sys
    from pathlib import Path
    SCRIPTS_DIR = Path(__file__).resolve().parents[1]
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.append(str(SCRIPTS_DIR))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev"]:
        d_path = str(SCRIPTS_DIR / domain)
        if d_path not in sys.path:
            sys.path.append(d_path)

import os
import sys
import uuid
import json
import shutil
from pathlib import Path

SHARED_DIR = Path(".agent/.shared")

def init():
    session_id = str(uuid.uuid4())
    session_path = SHARED_DIR / session_id
    session_path.mkdir(parents=True, exist_ok=True)
    
    state_file = session_path / "state.json"
    with open(state_file, "w") as f:
        json.dump({"status": "initialized", "tasks": {}}, f)
        
    print(session_id)
    return session_id

def close(session_id):
    session_path = SHARED_DIR / session_id
    if session_path.exists():
        shutil.rmtree(session_path)
        print(f"Session {session_id} closed and cleaned up.")
    else:
        print(f"Session {session_id} not found.")

def halt(session_id):
    session_path = SHARED_DIR / session_id
    if session_path.exists():
        halt_file = session_path / "HALT"
        halt_file.touch()
        print(f"Halt signal sent to session {session_id}.")
    else:
        print(f"Session {session_id} not found.")

def set_state(session_id, key, value):
    session_path = SHARED_DIR / session_id
    state_file = session_path / "state.json"
    if state_file.exists():
        with open(state_file, "r") as f:
            state = json.load(f)
        state[key] = value
        with open(state_file, "w") as f:
            json.dump(state, f, indent=2)
    else:
        print(f"Session {session_id} state file not found.")

def get_state(session_id):
    session_path = SHARED_DIR / session_id
    state_file = session_path / "state.json"
    if state_file.exists():
        with open(state_file, "r") as f:
            print(f.read())
    else:
        print(f"Session {session_id} state file not found.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: orchestration_session.py <init|close|halt|set-state|get-state> [args]")
        sys.exit(1)

    cmd = sys.argv[1]
    
    if cmd == "init":
        init()
    elif cmd == "close" and len(sys.argv) > 2:
        close(sys.argv[2])
    elif cmd == "halt" and len(sys.argv) > 2:
        halt(sys.argv[2])
    elif cmd == "set-state" and len(sys.argv) > 4:
        set_state(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "get-state" and len(sys.argv) > 2:
        get_state(sys.argv[2])
    else:
        print("Invalid command or missing arguments.")
        sys.exit(1)
