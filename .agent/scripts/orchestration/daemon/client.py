#!/usr/bin/env python3
"""
CLI Client for the agent squad orchestrator daemon.
Connects via UDS and manages tasks.
"""

import argparse
import json
import socket
import sys
import time
import uuid
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SOCKET_PATH = REPO_ROOT / ".agent" / "bus" / "orchestrator.sock"
DAEMON_SCRIPT = REPO_ROOT / ".agent" / "scripts" / "orchestration" / "daemon" / "server.py"


def bootstrap_daemon() -> bool:
    """Start the background daemon process if it is not running."""
    print("⏳ Orchestrator daemon is not running. Starting in background mode...")
    try:
        # Start server.py detached in the background
        # Redirect stdout/stderr to a log file
        log_dir = REPO_ROOT / ".agent" / "bus" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "daemon.log"

        with open(log_file, "a") as f:
            subprocess.Popen(
                [sys.executable, str(DAEMON_SCRIPT)],
                stdout=f,
                stderr=f,
                cwd=str(REPO_ROOT),
                preexec_fn=os.setsid if hasattr(os, "setsid") else None,
            )

        # Wait for the socket file to be created
        for _ in range(15):
            time.sleep(0.2)
            if SOCKET_PATH.exists():
                return True
        return False
    except Exception as e:
        print(f"❌ Daemon auto-start error: {e}")
        return False


def send_ipc_request(payload: dict) -> dict:
    """Connect to UDS socket, send JSON request, and read JSON response."""
    if not SOCKET_PATH.exists():
        if not bootstrap_daemon():
            print("❌ Error: failed to start the orchestrator daemon.")
            sys.exit(1)

    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.connect(str(SOCKET_PATH))
    except (ConnectionRefusedError, FileNotFoundError):
        # Stale socket or daemon died. Re-bootstrap.
        if bootstrap_daemon():
            try:
                s.connect(str(SOCKET_PATH))
            except Exception as e:
                print(f"❌ Failed to connect to the relaunched daemon: {e}")
                sys.exit(1)
        else:
            print("❌ Connection error: orchestrator daemon is unavailable.")
            sys.exit(1)

    try:
        req_data = json.dumps(payload).encode("utf-8") + b"\n"
        s.sendall(req_data)
        
        # Read response line by line
        resp_data = s.recv(65536)
        if not resp_data:
            return {"status": "error", "message": "Empty response from daemon."}
        
        return json.loads(resp_data.decode("utf-8").strip())
    except Exception as e:
        return {"status": "error", "message": f"IPC Communication error: {e}"}
    finally:
        s.close()


def monitor_task(task_id: str) -> None:
    """Connect to the daemon via attach streaming action and display real-time updates."""
    print(f"📺 Connecting to task session: {task_id} (streaming mode)...")

    if not SOCKET_PATH.exists():
        print("❌ Error: daemon socket not found.")
        return

    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.connect(str(SOCKET_PATH))
        req_data = json.dumps({"action": "attach", "task_id": task_id}).encode("utf-8") + b"\n"
        s.sendall(req_data)

        last_status = None
        last_node = None

        with s.makefile("r", encoding="utf-8") as f:
            for line in f:
                try:
                    res = json.loads(line.strip())
                except json.JSONDecodeError:
                    continue

                if res.get("status") == "error":
                    print(f"❌ {res.get('message')}")
                    break

                task = res.get("task", {})
                status = task.get("status", "unknown").upper()
                active_node = task.get("active_node", "unknown")

                if status != last_status or active_node != last_node:
                    print(f"🔄 [{status}] Active agent: @{active_node}")
                    last_status = status
                    last_node = active_node

                if status in ("COMPLETED", "FAILED"):
                    print(f"\n=== COMPLETION STATUS: {status} ===")
                    if task.get("test_results"):
                        print(f"Test results: {task.get('test_results')}")
                    break
    except Exception as e:
        print(f"❌ Streaming connection error: {e}")
    finally:
        s.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="CLI Facade client for Agent Squad Orchestrator Daemon.")
    parser.add_argument("--task", type=str, help="Task text to execute")
    parser.add_argument("--dry-run", action="store_true", help="Run in simulation mode")
    parser.add_argument("--scan-only", action="store_true", help="Print Mermaid graph and exit")
    parser.add_argument("--status", type=str, help="Check task status by its ID")
    parser.add_argument("--attach", type=str, help="Attach to active task session monitoring")
    parser.add_argument("--task-id", type=str, help="Specify custom task ID (optional)")

    # OS compatibility check for os module inside bootstrap
    global os
    import os

    args = parser.parse_args()

    if args.scan_only:
        res = send_ipc_request({"action": "scan_graph"})
        if res.get("status") == "success":
            print(res.get("mermaid"))
        else:
            print(f"❌ Error: {res.get('message')}")
        return

    if args.status:
        res = send_ipc_request({"action": "status", "task_id": args.status})
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return

    if args.attach:
        monitor_task(args.attach)
        return

    if args.task:
        task_id = args.task_id or f"task_{uuid.uuid4().hex[:8]}"
        res = send_ipc_request({
            "action": "run_task",
            "task_id": task_id,
            "task": args.task,
            "dry_run": args.dry_run
        })

        if res.get("status") == "error":
            print(f"❌ Launch error: {res.get('message')}")
            return

        print(f"🚀 Task launched successfully! Task ID: {task_id}")
        monitor_task(task_id)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
