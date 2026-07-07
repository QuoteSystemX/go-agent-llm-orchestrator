#!/usr/bin/env python3
"""
IPC server daemon for the agent squad orchestrator.
Listens on a Unix Domain Socket, executes tasks, and manages states.
"""

import asyncio
import json
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Any, Dict

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / ".agent" / "scripts"))

from lib.common import load_json_safe
from orchestration.squad_orchestrator import AgentScanner, GraphBuilder, ExecutionEngine
from orchestration.squad_schemas import TaskState
from orchestration.daemon.db import DaemonDB

logger = logging.getLogger("orchestrator.daemon")

SOCKET_PATH = REPO_ROOT / ".agent" / "bus" / "orchestrator.sock"
LOCK_NAME = "workspace"


class OrchestratorDaemon:
    """Manages the lifecycle, IPC socket connections, and task routing for the orchestrator."""

    def __init__(self, socket_path: Path = SOCKET_PATH) -> None:
        self.socket_path = socket_path
        self.db = DaemonDB()
        self.graph = None
        self.server = None
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.subscribers: Dict[str, list] = {}
        self.shutting_down = False

    def init_graph(self) -> None:
        """Scan agents, build/validate graph, and cache to DB."""
        logger.info("Scanning agent nodes...")
        scanner = AgentScanner()
        nodes = scanner.scan()
        builder = GraphBuilder(nodes)
        
        # Build and validate (will raise ValueError on cycle or missing nodes)
        self.graph = builder.build()
        logger.info("Agent graph validated successfully with %d nodes.", len(nodes))
        
        # Cache to SQLite
        self.db.cache_nodes(nodes)

    async def start(self) -> None:
        """Start the UDS socket server."""
        self.init_graph()

        # Clean up stale socket file if it exists
        if self.socket_path.exists():
            try:
                self.socket_path.unlink()
            except OSError as e:
                logger.error("Could not remove stale socket file %s: %s", self.socket_path, e)

        self.socket_path.parent.mkdir(parents=True, exist_ok=True)

        self.server = await asyncio.start_unix_server(
            self.handle_client,
            path=str(self.socket_path)
        )
        
        # Restrict socket permissions to 0600 (owner read-write only) for security
        try:
            os.chmod(str(self.socket_path), 0o600)
            logger.info("Restricted socket permissions on %s to 0600", self.socket_path)
        except OSError as e:
            logger.error("Failed to set socket permissions: %s", e)

        logger.info("Orchestrator daemon listening on %s", self.socket_path)

        # Handle system shutdown signals
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self.shutdown(s)))

        # Keep server running until shutdown is triggered
        async with self.server:
            await self.server.serve_forever()

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Handle incoming IPC messages from CLI/IDE clients."""
        keep_open = False
        try:
            data = await reader.readline()
            if not data:
                return

            request = json.loads(data.decode("utf-8").strip())
            action = request.get("action")
            task_id = request.get("task_id")

            logger.debug("Received request: action=%s, task_id=%s", action, task_id)

            if action == "run_task":
                response = await self.action_run_task(task_id, request.get("task"), request.get("dry_run", False))
            elif action == "status":
                response = self.action_status(task_id)
            elif action == "scan_graph":
                response = self.action_scan_graph()
            elif action == "attach":
                keep_open = True
                await self.action_attach(task_id, reader, writer)
                return
            else:
                response = {"status": "error", "message": f"Unknown action: '{action}'"}

            writer.write(json.dumps(response).encode("utf-8") + b"\n")
            await writer.drain()

        except Exception as e:
            logger.error("Error handling client request: %s", e)
            err_resp = {"status": "error", "message": str(e)}
            writer.write(json.dumps(err_resp).encode("utf-8") + b"\n")
            try:
                await writer.drain()
            except Exception:
                pass
        finally:
            if not keep_open:
                writer.close()
                await writer.wait_closed()

    async def action_attach(self, task_id: str, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Subscribe client to task status updates and stream them."""
        if not task_id:
            writer.write(json.dumps({"status": "error", "message": "Missing task_id"}).encode("utf-8") + b"\n")
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            return

        task_data = self.db.load_task(task_id)
        if not task_data:
            writer.write(json.dumps({"status": "error", "message": f"Task '{task_id}' not found."}).encode("utf-8") + b"\n")
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            return

        # Send initial status
        writer.write(json.dumps({"status": "update", "task": task_data}).encode("utf-8") + b"\n")
        await writer.drain()

        # If already completed or failed, close immediately
        if task_data.get("status") in ("completed", "failed"):
            writer.close()
            await writer.wait_closed()
            return

        # Subscribe
        self.subscribers.setdefault(task_id, []).append(writer)

        try:
            # Wait until client disconnects
            await reader.read()
        except Exception:
            pass
        finally:
            # Unsubscribe
            if task_id in self.subscribers and writer in self.subscribers[task_id]:
                self.subscribers[task_id].remove(writer)
            writer.close()
            await writer.wait_closed()

    async def action_run_task(self, task_id: str, task_desc: str, dry_run: bool) -> Dict[str, Any]:
        """Locks the workspace, schedules execution in the background, and returns execution status."""
        if not task_id or not task_desc:
            return {"status": "error", "message": "Missing task_id or task description."}

        # Try to acquire workspace lock (Idempotency and concurrency safety)
        # Holder is the task_id
        acquired = self.db.acquire_lock(LOCK_NAME, task_id, ttl_seconds=1800.0) # 30 mins limit
        if not acquired:
            # Check if this task is already running (idempotency key)
            if task_id in self.active_tasks:
                return {"status": "running", "task_id": task_id, "message": "Task is already executing."}
            return {
                "status": "error",
                "message": "Workspace is currently locked by another task run. Please wait."
            }

        # Setup task state in DB
        state = TaskState(issue_description=task_desc, status="planning")
        self.db.save_task(task_id, state.model_dump())

        # Spawn background execution task
        coro = self._execute_task_in_background(task_id, state, dry_run)
        async_task = asyncio.create_task(coro)
        self.active_tasks[task_id] = async_task

        return {"status": "started", "task_id": task_id, "message": "Task execution started in background."}

    async def _execute_task_in_background(self, task_id: str, state: TaskState, dry_run: bool) -> None:
        """Run the ExecutionEngine and persist trace/release locks on completion."""
        try:
            logger.info("Starting background execution for task %s", task_id)
            engine = ExecutionEngine(self.graph, dry_run=dry_run)
            
            # Wrap execution engine run inside a thread pool since query_llm_safe
            # and subprocess.run are blocking CPU-bound calls.
            loop = asyncio.get_running_loop()
            
            def run_sync():
                # We inject DB persistence into the traversal loop
                # Let's override visit helper to write progress to SQLite WAL
                original_visit = engine._visit
                def patched_visit(agent_name: str, task_state: TaskState):
                    original_visit(agent_name, task_state)
                    # Persist state update to DB on each node visit
                    self.db.save_task(task_id, task_state.model_dump())
                    # Broadcast update to subscribers
                    loop.call_soon_threadsafe(self.broadcast, task_id, task_state.model_dump())
                
                engine._visit = patched_visit
                return engine.run(state)

            final_state = await loop.run_in_executor(None, run_sync)
            
            # Save final task state
            self.db.save_task(task_id, final_state.model_dump())
            
            # Save final trace log to DB
            self.db.save_trace(engine._session_id, task_id, engine._trace)
            logger.info("Background execution for task %s finished with status: %s", task_id, final_state.status)
            
            # Broadcast completion
            self.broadcast(task_id, final_state.model_dump())

        except Exception as e:
            logger.error("Exception during background task execution %s: %s", task_id, e)
            state.status = "failed"
            self.db.save_task(task_id, state.model_dump())
        finally:
            # Release workspace lock
            self.db.release_lock(LOCK_NAME, task_id)
            self.active_tasks.pop(task_id, None)

    def broadcast(self, task_id: str, state_dict: Dict[str, Any]) -> None:
        """Broadcast status update to all connected subscribers."""
        writers = self.subscribers.get(task_id, [])
        if not writers:
            return
        
        logger.debug("Broadcasting task %s update to %d subscribers", task_id, len(writers))
        data = json.dumps({"status": "update", "task": state_dict}).encode("utf-8") + b"\n"
        
        # Safe thread-safe broadcast execution
        loop = asyncio.get_event_loop()
        
        async def _write(w):
            try:
                w.write(data)
                await w.drain()
            except Exception:
                pass

        for w in list(writers):
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(_write(w), loop)

    def action_status(self, task_id: str) -> Dict[str, Any]:
        """Fetch the current status of a task from the DB."""
        if not task_id:
            return {"status": "error", "message": "Missing task_id."}
        task_data = self.db.load_task(task_id)
        if not task_data:
            return {"status": "error", "message": f"Task '{task_id}' not found."}
        return {"status": "success", "task": task_data}

    def action_scan_graph(self) -> Dict[str, Any]:
        """Scan the agent nodes and return the Mermaid diagram structure."""
        if not self.graph:
            return {"status": "error", "message": "Graph not initialized."}
        builder = GraphBuilder(list(self.graph.nodes.values()))
        mermaid = builder.to_mermaid(self.graph)
        return {"status": "success", "mermaid": mermaid}

    async def shutdown(self, sig: signal.Signals) -> None:
        """Gracefully close sockets and terminate background tasks."""
        if self.shutting_down:
            return
        self.shutting_down = True
        logger.info("Received signal %s. Initiating graceful shutdown...", sig.name)

        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("IPC Socket server stopped.")

        # Clean up socket file
        if self.socket_path.exists():
            try:
                self.socket_path.unlink()
            except OSError as e:
                logger.error("Error removing socket file: %s", e)

        # Wait for active background tasks to finish
        if self.active_tasks:
            logger.info("Waiting for %d active background task(s) to finish...", len(self.active_tasks))
            # Wait up to 10 seconds for tasks to complete
            try:
                await asyncio.wait(list(self.active_tasks.values()), timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning("Timeout waiting for background tasks. Terminating.")

        logger.info("Graceful shutdown complete.")
        sys.exit(0)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    daemon = OrchestratorDaemon()
    try:
        asyncio.run(daemon.start())
    except Exception as e:
        logger.fatal("Failed to run orchestrator daemon: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
