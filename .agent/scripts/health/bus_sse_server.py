#!/usr/bin/env python3
"""Lightweight SSE server for live dashboard updates.

Usage:
    python3 bus_sse_server.py [--port 3201] [--bus-dir .agent/bus]

Endpoints:
    GET  /                       → dashboard.html
    GET  /api/health             → current health report JSON
    GET  /api/stream/bus         → SSE stream of bus file changes
    GET  /data/metrics_history.jsonl  → sparkline history
    POST /api/exec               → execute allowed script (Cockpit Ops)

Press Ctrl+C to stop.
"""

import os, sys, json, time, threading, re, subprocess, socket
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from http.server import ThreadingHTTPServer
except ImportError:
    from socketserver import ThreadingMixIn
    class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
        daemon_threads = True
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
BUS_DIR = REPO_ROOT / ".agent" / "bus"
DATA_DIR = REPO_ROOT / ".agent" / "data"
DASHBOARD_PATH = REPO_ROOT / ".agent" / "dashboard.html"
HISTORY_PATH = DATA_DIR / "metrics_history.jsonl"
WATCHDOG_PATH = REPO_ROOT / ".agent" / "config" / "watchdog_rules.json"
ORCHESTRATOR_SOCKET_PATH = REPO_ROOT / ".agent" / "bus" / "orchestrator.sock"

# Import existing WSL detection logic from the project
if str(SCRIPT_DIR.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR.parent))

try:
    from lib.common import _is_wsl as is_wsl
except ImportError:
    def is_wsl() -> bool:
        """Detect if running under Windows Subsystem for Linux."""
        try:
            with open("/proc/version", "r") as f:
                return "microsoft" in f.read().lower() or "wsl" in f.read().lower()
        except Exception:
            return False

def send_uds_request(payload: dict) -> dict:
    """Connect to orchestrator UDS, send payload, and receive JSON response."""
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.connect(str(ORCHESTRATOR_SOCKET_PATH))
        req_data = json.dumps(payload).encode("utf-8") + b"\n"
        s.sendall(req_data)
        
        resp_data = s.recv(65536)
        if not resp_data:
            return {"status": "error", "message": "Empty response from orchestrator daemon."}
        return json.loads(resp_data.decode("utf-8").strip())
    except Exception as e:
        return {"status": "error", "message": f"UDS Connection failed: {e}"}
    finally:
        s.close()


POLL_INTERVAL = 1.0  # seconds
PORT = 3201

# ── Allowed scripts for Cockpit Ops (Option C) ──
ALLOWED_SCRIPTS = {
    "status-report": {
        "cmd": ["python3", str(SCRIPT_DIR / "status_report.py"), "--html"],
        "desc": "Regenerate dashboard",
    },
    "checklist-fix": {
        "cmd": ["python3", str(REPO_ROOT / ".agent" / "scripts" / "dev" / "checklist.py"), ".", "--fix"],
        "desc": "Run auto-fix checklist",
    },
    "security-scan": {
        "cmd": ["python3", str(REPO_ROOT / ".agent" / "scripts" / "health" / "security_scan.py")],
        "desc": "Run security scan",
    },
    "sync-docs": {
        "cmd": ["python3", str(REPO_ROOT / ".agent" / "scripts" / "dev" / "doc_healer.py")],
        "desc": "Sync documentation",
    },
    "chaos-drill": {
        "cmd": ["python3", str(REPO_ROOT / ".agent" / "scripts" / "chaos" / "chaos_monkey.py")],
        "desc": "Trigger chaos drill",
    },
}

# ── Bus file → metric name mapping for SSE updates ──
BUS_METRIC_MAP = {
    "budget_status.json": "Budget",
    "mcp_health_metrics.json": "MCP Services",
    "blue_team_status.json": "Stability",
    "ki_coverage_metrics.json": "KI Coverage",
    "intelligence_roi_metrics.json": "Intelligence ROI",
    "linter_debt_metrics.json": "Linter Debt",
    "chaos_report.json": "Resilience",
    "sync_parity_metrics.json": "Sync Status",
    "hallucination_report.json": "Ethics Audit",
    "policy_report.json": "Policy Compliance",
    "seo_metrics.json": "SEO Check",
    "ux_metrics.json": "UX Audit",
    "dead_code_metrics.json": "Dead Code",
}

# ── SSE client registry ──
sse_clients = []
sse_lock = threading.Lock()

class SSEHandler(BaseHTTPRequestHandler):
    """HTTP handler that serves static files and SSE streams."""

    def log_message(self, format, *args):
        """Silence default logging (too noisy for SSE)."""
        if "GET /api/stream/bus" not in str(args):
            print(f"[SSE] {args[0]} {args[1]} {args[2]}")

    def _send_json(self, status, data, mime="application/json"):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_file_or_404(self, path: Path, mime="text/html"):
        if not path.exists() or not path.is_file():
            self._send_json(404, {"error": "not found"})
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache, must-revalidate")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]  # strip query params

        if path == "/" or path == "/index.html":
            self._read_file_or_404(DASHBOARD_PATH, "text/html")

        elif path == "/api/health":
            self._handle_health()

        elif path == "/api/stream/bus":
            self._handle_sse()

        elif path.startswith("/api/output/"):
            exec_id = path.split("/api/output/")[1].split("/")[0]
            self._handle_output(exec_id)

        elif path == "/api/orchestrator/graph":
            res = send_uds_request({"action": "scan_graph"})
            self._send_json(200 if res.get("status") == "success" else 500, res)

        elif path.startswith("/api/orchestrator/status/"):
            task_id = path.split("/api/orchestrator/status/")[1].split("/")[0]
            res = send_uds_request({"action": "status", "task_id": task_id})
            self._send_json(200 if res.get("status") != "error" else 500, res)

        elif path.startswith("/api/orchestrator/stream/"):
            task_id = path.split("/api/orchestrator/stream/")[1].split("/")[0]
            self._handle_orchestrator_stream(task_id)

        elif path == "/data/metrics_history.jsonl":
            mime = "text/plain" if not HISTORY_PATH.exists() else "application/x-ndjson"
            self._read_file_or_404(HISTORY_PATH, mime)

        elif path.startswith("/static/"):
            static_path = REPO_ROOT / ".agent" / path.lstrip("/")
            ext = path.split(".")[-1]
            mime_map = {"html": "text/html", "css": "text/css", "js": "application/javascript",
                        "json": "application/json", "svg": "image/svg+xml", "png": "image/png"}
            self._read_file_or_404(static_path, mime_map.get(ext, "text/plain"))

        else:
            self._send_json(404, {"error": f"no such endpoint: {path}"})

    def do_POST(self):
        if self.path == "/api/exec":
            self._handle_exec()
        elif self.path == "/api/orchestrator/run":
            self._handle_orchestrator_run()
        else:
            self._send_json(404, {"error": "not found"})

    # ── SSE Stream ──
    def _handle_sse(self):
        """Handle SSE connection — keep open and push bus updates."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        client_id = id(self)
        with sse_lock:
            sse_clients.append(client_id)

        try:
            # Send initial "connected" event with current bus state
            initial = self._gather_bus_state()
            self._sse_send("connected", initial)

            # Track file mtimes
            last_mtimes = self._scan_bus_mtimes()

            while True:
                time.sleep(POLL_INTERVAL)
                current_mtimes = self._scan_bus_mtimes()
                changes = {}
                for fname, mtime in current_mtimes.items():
                    if fname not in last_mtimes or mtime > last_mtimes[fname]:
                        fpath = BUS_DIR / fname
                        try:
                            content = json.loads(fpath.read_text())
                            changes[fname] = {"content": content, "metric": BUS_METRIC_MAP.get(fname)}
                        except Exception:
                            changes[fname] = {"content": None, "metric": BUS_METRIC_MAP.get(fname)}
                if changes:
                    last_mtimes.update(current_mtimes)
                    self._sse_send("bus_update", changes)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            with sse_lock:
                if client_id in sse_clients:
                    sse_clients.remove(client_id)

    def _sse_send(self, event: str, data):
        """Write an SSE event to the wire."""
        try:
            payload = json.dumps(data)
            self.wfile.write(f"event: {event}\ndata: {payload}\n\n".encode())
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            raise

    def _scan_bus_mtimes(self):
        """Return dict of {filename: mtime} for all bus JSON files."""
        mtimes = {}
        if not BUS_DIR.exists():
            return mtimes
        for f in BUS_DIR.iterdir():
            if f.suffix == ".json" and f.is_file():
                mtimes[f.name] = f.stat().st_mtime
        return mtimes

    def _gather_bus_state(self):
        """Read all bus JSON files and return their contents."""
        state = {}
        if not BUS_DIR.exists():
            return state
        for f in sorted(BUS_DIR.iterdir()):
            if f.suffix == ".json" and f.is_file():
                try:
                    state[f.name] = json.loads(f.read_text())
                except Exception:
                    state[f.name] = None
        return state

    # ── Health Report ──
    def _handle_health(self):
        """Return the latest health report from cached bus data."""
        try:
            sys.path.insert(0, str(SCRIPT_DIR))
            sys.path.insert(0, str(SCRIPT_DIR.parent))
            from status_report import get_health_report
            report = get_health_report()
            self._send_json(200, report)
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    # ── Cockpit Exec (Option C) ──
    def _handle_exec(self):
        """Execute an allowed script and stream output back."""
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len) if content_len else b"{}"
        try:
            req = json.loads(body)
        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid JSON"})
            return

        script_key = req.get("script", "")
        if script_key not in ALLOWED_SCRIPTS:
            self._send_json(403, {"error": f"script '{script_key}' not allowed"})
            return

        script_info = ALLOWED_SCRIPTS[script_key]
        cmd = script_info["cmd"]

        # Validate against watchdog rules
        try:
            sys.path.insert(0, str(SCRIPT_DIR.parent))
            from health.guardrail_monitor import check_command_safety
            result = check_command_safety(" ".join(cmd))
            if result == "block":
                self._send_json(403, {"error": "command blocked by guardrail"})
                return
        except Exception:
            pass  # proceed if guardrail unavailable

        # Execute and stream: send 202 + exec_id
        exec_id = f"exec_{int(time.time())}"
        self._send_json(202, {
            "exec_id": exec_id,
            "script": script_key,
            "desc": script_info["desc"],
        })

        # Background thread for execution with SSE broadcast
        def _run():
            try:
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, cwd=str(REPO_ROOT)
                )
                for line in iter(proc.stdout.readline, ""):
                    if line:
                        data = json.dumps({"exec_id": exec_id, "line": line.rstrip()})
                        with sse_lock:
                            for cid in list(sse_clients):
                                pass  # SSE broadcast handled by client polling
                        # Also write to bus for SSE clients to pick up
                        out_dir = BUS_DIR / "outputs"
                        out_dir.mkdir(parents=True, exist_ok=True)
                        log_path = out_dir / f"{exec_id}.jsonl"
                        with open(log_path, "a") as lf:
                            lf.write(f"{json.dumps({'line': line.rstrip()})}\n")
                proc.wait()
                # Signal completion
                with open(log_path, "a") as lf:
                    lf.write(f"{json.dumps({'done': True, 'code': proc.returncode})}\n")
            except Exception as e:
                pass

        threading.Thread(target=_run, daemon=True).start()

    # ── Exec Output Reader ──
    def _handle_output(self, exec_id: str):
        """Return accumulated output lines for a given exec_id."""
        out_dir = BUS_DIR / "outputs"
        log_path = out_dir / f"{exec_id}.jsonl"
        if not log_path.exists():
            self._send_json(404, {"error": f"no output for {exec_id}"})
            return
        lines = []
        done = False
        code = None
        try:
            with open(log_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        if "done" in entry:
                            done = entry["done"]
                            code = entry.get("code")
                        else:
                            lines.append(entry.get("line", ""))
                    except json.JSONDecodeError:
                        lines.append(line)
        except Exception as e:
            self._send_json(500, {"error": str(e)})
            return
        self._send_json(200, {
            "exec_id": exec_id,
            "lines": lines,
            "done": done,
            "code": code,
        })

    # ── Orchestrator Daemon Proxy ──
    def _handle_orchestrator_run(self):
        """Send run task request to orchestrator daemon."""
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len) if content_len else b"{}"
        try:
            req = json.loads(body)
        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid JSON"})
            return

        task_desc = req.get("task", "")
        task_id = req.get("task_id", "")
        dry_run = req.get("dry_run", False)

        if not task_desc:
            self._send_json(400, {"error": "Missing task description"})
            return

        import uuid
        if not task_id:
            task_id = f"task_{uuid.uuid4().hex[:8]}"

        payload = {
            "action": "run_task",
            "task_id": task_id,
            "task": task_desc,
            "dry_run": dry_run
        }
        res = send_uds_request(payload)
        self._send_json(200, res)

    def _handle_orchestrator_stream(self, task_id: str):
        """Connect to orchestrator socket 'attach' action and stream logs as SSE."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            s.connect(str(ORCHESTRATOR_SOCKET_PATH))
            req_payload = {"action": "attach", "task_id": task_id}
            s.sendall(json.dumps(req_payload).encode("utf-8") + b"\n")
            
            with s.makefile("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        res = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    
                    self.wfile.write(f"event: update\ndata: {json.dumps(res)}\n\n".encode("utf-8"))
                    self.wfile.flush()
                    
                    # If completed or failed, we can terminate the SSE stream
                    task_data = res.get("task", {})
                    status = task_data.get("status", "").lower()
                    if status in ("completed", "failed"):
                        break
        except Exception as e:
            err_resp = {"status": "error", "message": f"SSE UDS stream error: {e}"}
            try:
                self.wfile.write(f"event: error\ndata: {json.dumps(err_resp)}\n\n".encode("utf-8"))
                self.wfile.flush()
            except Exception:
                pass
        finally:
            s.close()



def get_wsl_ip() -> str:
    """Get the WSL network interface IP address."""
    # Method 1: Try connecting to a dummy socket to find local interface IP used for routing
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        pass

    # Method 2: Try running 'hostname -I'
    try:
        ips = subprocess.check_output(["hostname", "-I"], text=True).strip().split()
        if ips:
            return ips[0]
    except Exception:
        pass

    # Method 3: Fallback to socket gethostbyname
    try:
        return socket.gethostbyname(socket.gethostname())
    except Exception:
        return "127.0.0.1"


def start_server(port=None, bus_dir=None):
    """Start the SSE HTTP server with automatic port selection and WSL support."""
    global BUS_DIR
    if bus_dir:
        BUS_DIR = Path(bus_dir)

    if port is None:
        port = 3207 if is_wsl() else 3201

    server = None
    for attempt in range(10):
        try:
            server = ThreadingHTTPServer(("0.0.0.0", port), SSEHandler)
            break
        except OSError as e:
            if e.errno == 98 or "already in use" in str(e).lower():
                print(f"  ⚠️  Port {port} is already in use. Trying next port...")
                port += 1
            else:
                raise e

    if not server:
        print("  ❌ Could not find an open port to bind to.")
        sys.exit(1)

    wsl_ip = None
    if is_wsl():
        wsl_ip = get_wsl_ip()

    if wsl_ip:
        print(f"  🔴 SSE Bus Server:    http://{wsl_ip}:{port}/  (WSL IP)")
        print(f"                        http://localhost:{port}/")
        print(f"  📡 SSE Stream:        http://{wsl_ip}:{port}/api/stream/bus")
        print(f"  📊 Health API:        http://{wsl_ip}:{port}/api/health")
        print(f"  ⚡ Cockpit Exec:      POST http://{wsl_ip}:{port}/api/exec")
    else:
        print(f"  🔴 SSE Bus Server:    http://localhost:{port}/")
        print(f"  📡 SSE Stream:        http://localhost:{port}/api/stream/bus")
        print(f"  📊 Health API:        http://localhost:{port}/api/health")
        print(f"  ⚡ Cockpit Exec:      POST http://localhost:{port}/api/exec")
    print(f"  📁 Serving dashboard: {DASHBOARD_PATH}")
    print(f"  👀 Watching:          {BUS_DIR}")
    print(f"  🔄 Poll interval:     {POLL_INTERVAL}s")
    print(f"  🛑 Press Ctrl+C to stop\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  ⏹️  SSE server stopped.")
        server.server_close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Live Dashboard SSE Server")
    parser.add_argument("--port", type=int, default=None, help="Port (default: 3207 in WSL, else 3201)")
    parser.add_argument("--bus-dir", type=str, default=str(BUS_DIR), help="Bus directory path")
    args = parser.parse_args()
    start_server(port=args.port, bus_dir=args.bus_dir)
