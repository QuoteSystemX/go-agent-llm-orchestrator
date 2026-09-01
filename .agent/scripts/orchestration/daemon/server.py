#!/usr/bin/env python3
"""
IPC server daemon for the agent squad orchestrator.
Listens on a Unix Domain Socket, executes tasks, and manages states.
"""

import asyncio
import datetime
import json
import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / ".agent" / "scripts"))

from lib.common import load_json_safe
from orchestration.squad_orchestrator import AgentScanner, GraphBuilder, ExecutionEngine
from orchestration.squad_schemas import TaskState
from orchestration.daemon.db import DaemonDB

logger = logging.getLogger("orchestrator.daemon")

SOCKET_PATH = REPO_ROOT / ".agent" / "bus" / "orchestrator.sock"
LOCK_NAME = "workspace"

# STORY-3.3 gate G: file-based fallback kill switch (ADR-007 §6.3). Written
# by `bin/stop --kill` when the primary UDS IPC path is unavailable. Poll
# interval, not a "5s tick" as bin/stop's help text previously (falsely)
# claimed — nothing read this file at all until this fix.
FALLBACK_STOP_FILE = REPO_ROOT / ".agent" / "STOP"
FALLBACK_STOP_POLL_INTERVAL_S = float(os.environ.get("DAEMON_STOP_POLL_INTERVAL_S", "2.0"))



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

        self._clear_stale_stop_file()
        loop.create_task(self._watch_fallback_stop_file())

        # Keep server running until shutdown is triggered
        async with self.server:
            await self.server.serve_forever()

    def _clear_stale_stop_file(self) -> None:
        """STORY-3.3 gate G: discard a STOP file predating this process start.

        A file left over from a previous kill attempt (or a crash before it
        could be consumed) is ambiguous, not necessarily an active kill
        request against *this* freshly-started process — treat it as
        cleanup, log it, and move on, so a fresh daemon doesn't immediately
        self-terminate on startup. `_watch_fallback_stop_file` only reacts
        to files that appear after this point.
        """
        if FALLBACK_STOP_FILE.exists():
            logger.warning(
                "Stale fallback STOP file found at startup (%s) — removing without acting on it.",
                FALLBACK_STOP_FILE,
            )
            try:
                FALLBACK_STOP_FILE.unlink()
            except OSError as e:
                logger.error("Could not remove stale STOP file: %s", e)

    async def _watch_fallback_stop_file(self) -> None:
        """STORY-3.3 gate G: poll for the fallback kill-switch file.

        `bin/stop --kill` writes FALLBACK_STOP_FILE when the primary UDS IPC
        path is unavailable — the exact scenario this exists for. Previously
        nothing read it (bin/stop's own comment claimed a "5s tick" that
        never existed anywhere in this file); found in the 2026-08-12 audit.
        Reuses the same idempotent `shutdown()` the signal handlers and
        `action_stop` call, and persists its own `daemon_stop_fallback`
        audit event (distinct from `action_stop`'s `daemon_stop` event) so
        it's observable which path actually triggered a given shutdown.
        """
        while not self.shutting_down:
            if FALLBACK_STOP_FILE.exists():
                reason = (
                    FALLBACK_STOP_FILE.read_text(encoding="utf-8", errors="replace").strip()
                    or "fallback STOP file detected, no reason given"
                )
                logger.warning("Fallback STOP file detected — initiating shutdown. %s", reason)

                try:
                    bus_dir = REPO_ROOT / ".agent" / "bus"
                    bus_dir.mkdir(parents=True, exist_ok=True)
                    event = {
                        "id": f"stop_fallback_{int(datetime.datetime.utcnow().timestamp())}",
                        "type": "daemon_stop_fallback",
                        "author": "daemon._watch_fallback_stop_file",
                        "reason": reason,
                        "active_tasks_at_stop": list(self.active_tasks.keys()),
                        "ts": datetime.datetime.utcnow().isoformat() + "Z",
                    }
                    with open(bus_dir / "daemon_stop.jsonl", "a", encoding="utf-8") as f:
                        f.write(json.dumps(event) + "\n")
                except Exception as e:
                    logger.warning("Could not persist fallback stop event to bus: %s", e)

                # Remove before shutting down, not after: shutdown() can take
                # up to 10s waiting on active tasks, and a lingering file
                # would otherwise look "stale but present" to the startup
                # check if the process were killed mid-shutdown and restarted.
                try:
                    FALLBACK_STOP_FILE.unlink()
                except OSError:
                    pass

                await self.shutdown(signal.SIGTERM)
                return
            await asyncio.sleep(FALLBACK_STOP_POLL_INTERVAL_S)

    # STORY-4: Map action → required capability for capability_check.
    # Each privileged action must be authorized by the caller's role.
    # Read-only actions (status, daemon_status) are public — no check.
    ACTION_CAPABILITY_MAP = {
        "run_task": "modify-tasks",
        "stop": "stop-daemon",
        "trigger_distill": "trigger-distill",
    }

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
            # STORY-4: caller_role is required for privileged actions. Default
            # is "human" (backward compatible with existing CLI tools like
            # bin/stop). For non-human callers, the payload must include
            # caller_role explicitly. bin/harness_run and bin/orchestrate
            # should pass "infra-agent" or "squad-agent".
            caller_role = request.get("caller_role", "human")
            scope = request.get("scope", "global")

            logger.debug("Received request: action=%s, task_id=%s, caller=%s",
                         action, task_id, caller_role)

            # STORY-4: Capability check (default-deny). For privileged
            # actions, verify the caller's role is allowed in the matrix.
            if action in self.ACTION_CAPABILITY_MAP:
                cap = self.ACTION_CAPABILITY_MAP[action]
                denial = self._check_capability(caller_role, cap, scope)
                if denial:
                    logger.warning("Capability denied: %s denied %s on %s", caller_role, cap, scope)
                    # B5: emit capability_denied bus event for telemetry
                    self._emit_capability_denied(action, caller_role, cap, scope)
                    response = denial
                    writer.write(json.dumps(response).encode("utf-8") + b"\n")
                    await writer.drain()
                    return

            if action == "run_task":
                response = await self.action_run_task(task_id, request.get("task"), request.get("dry_run", False))
            elif action == "status":
                response = self.action_status(task_id)
            elif action == "scan_graph":
                response = self.action_scan_graph()
            elif action == "daemon_status":
                response = self.action_daemon_status()
            elif action == "stop":
                response = await self.action_stop(request.get("reason", "no reason provided"))
            elif action == "trigger_distill":
                # STORY-1: Manual trigger of the memory-pressure distill pipeline.
                # Useful from CI or pre-commit hooks. The actual work runs
                # synchronously in this handler thread, so the caller gets the
                # full result before the next request is processed.
                loop = asyncio.get_running_loop()
                response = await loop.run_in_executor(
                    None, self.trigger_pressure_distill, request.get("reason", "manual")
                )
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

        # STORY-3.3: Refuse new tasks when daemon is draining (graceful shutdown).
        # The stop is acknowledged by the daemon BEFORE new requests are processed,
        # so any client that received a stop ACK is guaranteed to see this gate.
        if self.shutting_down:
            return {
                "status": "error",
                "message": "Daemon is draining (graceful shutdown in progress). New tasks refused.",
                "code": "DAEMON_DRAINING",
            }

        # STORY-2: Inject sanitized INBOX fragments into the task description.
        # The daemon reads the human's INBOX.md at task start and prepends a
        # sanitized fragment to the task description. The strip_for_prompt()
        # function removes dangerous markup (defense-in-depth) before injection.
        inbox_fragment = self._build_inbox_fragment(target=task_id)
        if inbox_fragment:
            task_desc = f"{inbox_fragment}\n\n---\n\n{task_desc}"

        # STORY-6: Inject distilled lessons (knowledge compounding).
        # After archivist_trigger runs, fresh lessons are registered for
        # re-injection. The daemon prepending them here closes the loop:
        # distillation is no longer "write-only" — agents immediately see
        # what was learned.
        knowledge_fragment = self._build_knowledge_fragment(scope="global")
        if knowledge_fragment:
            task_desc = f"{knowledge_fragment}\n\n---\n\n{task_desc}"

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

        async def _write(w: asyncio.StreamWriter) -> None:
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

    def action_daemon_status(self) -> Dict[str, Any]:
        """Return current daemon state (STORY-3.3 SIGTERM channel).

        State machine:
            - running:   accepting new tasks, normal operation
            - draining:  shutting down, refuses new tasks, in-flight finishing
            - stopped:   fully shut down (after shutdown() completes)
        """
        if self.shutting_down:
            state = "draining"
        else:
            state = "running"
        return {
            "status": "success",
            "state": state,
            "active_tasks": list(self.active_tasks.keys()),
            "socket_path": str(self.socket_path),
        }

    def _check_capability(self, role: str, capability: str, scope: str = "global"):
        """STORY-4: Default-deny capability check for privileged IPC actions.

        Takes a capability NAME (e.g., "modify-tasks") and checks if the
        role's capability list in the matrix contains it. Returns None
        if allowed, or a denial response dict if denied.

        Note: This is different from capability_check.check() which takes
        an OPERATION key and looks up the cap name via the operations table.
        The daemon uses cap names directly (mapped from action via
        ACTION_CAPABILITY_MAP) so we iterate role capabilities directly.

        Fail-open behavior: if the capability matrix is unavailable
        (e.g., not deployed), this returns None (allow). This matches
        the pre-capability-matrix behavior. The capability_audit.py
        script (separate) should detect and flag missing matrices.
        """
        try:
            sys.path.insert(0, str(REPO_ROOT / ".agent" / "scripts" / "permissions"))
            from capability_check import load_matrix  # type: ignore
            matrix = load_matrix()
        except Exception as e:
            logger.debug("Capability matrix unavailable, fail-open: %s", e)
            return None

        role_data = matrix.get("roles", {}).get(role)
        if not role_data:
            return self._deny(role, capability, scope, "unknown role")
        caps = role_data.get("capabilities", [])
        target_scope = scope or "global"
        for cap_entry in caps:
            if not isinstance(cap_entry, dict):
                continue
            if cap_entry.get("cap") != capability:
                continue
            # Scope match (reuse the matrix's scope matching semantics)
            cap_scope = cap_entry.get("scope", "global")
            if cap_scope == "global" or cap_scope == target_scope:
                return None  # allowed
            if cap_scope.endswith(":*") and target_scope.startswith(cap_scope[:-1]):
                return None
        return self._deny(role, capability, scope, "not in role's capability list")

    def _deny(self, role: str, capability: str, scope: str, reason: str):
        return {
            "status": "error",
            "code": "CAPABILITY_DENIED",
            "message": (
                f"Capability denied: role='{role}' capability='{capability}' "
                f"scope='{scope}' reason='{reason}'. See .agent/config/capabilities.yaml."
            ),
            "required_capability": capability,
            "caller_role": role,
            "scope": scope,
        }

    def _emit_capability_denied(self, action: str, role: str, capability: str, scope: str) -> None:
        """B5: emit a bus event for telemetry when a capability check fails.

        Writes to .agent/bus/capability_denied.jsonl (best-effort).
        """
        try:
            bus_dir = REPO_ROOT / ".agent" / "bus"
            bus_dir.mkdir(parents=True, exist_ok=True)
            event = {
                "type": "capability_denied",
                "action": action,
                "caller_role": role,
                "required_capability": capability,
                "scope": scope,
                "ts": datetime.datetime.utcnow().isoformat() + "Z",
            }
            with open(bus_dir / "capability_denied.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
        except Exception as e:
            logger.debug("Could not emit capability_denied event: %s", e)

    def _build_inbox_fragment(self, target: Optional[str] = None, max_chars: int = 4000) -> str:
        """STORY-2: Build a sanitized INBOX fragment for system-prompt injection.

        Reads entries from tasks/INBOX.md, filters by target (if given), and
        returns a strip_for_prompt() formatted string. Returns empty string if
        the inbox is empty or the communication module is unavailable.
        """
        try:
            sys.path.insert(0, str(REPO_ROOT / ".agent" / "scripts" / "communication"))
            from inbox import read_entries, strip_for_prompt  # type: ignore
        except Exception as e:
            logger.debug("INBOX module unavailable: %s", e)
            return ""
        try:
            entries = read_entries(target=target, include_acked=False)
            if not entries:
                return ""
            fragment = strip_for_prompt(entries, max_chars=max_chars)
            if fragment:
                logger.info("Injected %d INBOX entries into task %s", len(entries), target or "(global)")
            return fragment
        except Exception as e:
            logger.warning("Failed to build INBOX fragment: %s", e)
            return ""

    def _build_knowledge_fragment(self, scope: str = "global", max_chars: int = 4000) -> str:
        """STORY-6: Build a fragment of distilled lessons for prompt injection.

        Closes the distillation loop: lessons extracted by archivist_trigger
        are registered in the injection index, then re-injected into the
        next session's task description. The fragment is plain text (no
        markup); sanitization is automatic since the source is markdown
        with a strict format.

        Returns empty string if no active injections or module unavailable.
        """
        try:
            sys.path.insert(0, str(REPO_ROOT / ".agent" / "scripts" / "communication"))
            from knowledge_inject import build_knowledge_fragment  # type: ignore
        except Exception as e:
            logger.debug("knowledge_inject module unavailable: %s", e)
            return ""
        try:
            fragment = build_knowledge_fragment(scope=scope, max_chars=max_chars)
            if fragment:
                logger.info("Injected knowledge fragment (scope=%s, %d chars)", scope, len(fragment))
            return fragment
        except Exception as e:
            logger.warning("Failed to build knowledge fragment: %s", e)
            return ""

    def trigger_pressure_distill(self, reason: str = "manual") -> Dict[str, Any]:
        """STORY-1: Run agent_squeeze + experience_distiller synchronously.

        Returns a structured result with which steps ran, durations, and any
        errors. Designed to be safe to call from a thread executor AND from
        a synchronous context (no event loop required).
        """
        started = time.time()
        result: Dict[str, Any] = {
            "status": "success",
            "reason": reason,
            "started_ts": datetime.datetime.utcnow().isoformat() + "Z",
            "steps": [],
        }

        # Step 1: agent_squeeze (compresses in-memory state to LESSONS)
        step_start = time.time()
        try:
            from knowledge import agent_squeeze  # type: ignore
            agent_squeeze.main()
            result["steps"].append({"name": "agent_squeeze", "status": "ok", "duration_s": round(time.time() - step_start, 3)})
        except Exception as e:
            logger.exception("agent_squeeze failed during pressure distill")
            result["steps"].append({"name": "agent_squeeze", "status": "error", "error": str(e)})
            result["status"] = "partial"

        # Step 2: experience_distiller (archives old lessons)
        try:
            step_start = time.time()
            from knowledge import experience_distiller  # type: ignore
            distill_result = experience_distiller.distill_lessons()
            result["steps"].append({"name": "experience_distiller", "status": "ok", "summary": distill_result, "duration_s": round(time.time() - step_start, 3)})
        except Exception as e:
            logger.exception("experience_distiller failed during pressure distill")
            result["steps"].append({"name": "experience_distiller", "status": "error", "error": str(e)})
            result["status"] = "partial"

        return result

    async def action_stop(self, reason: str) -> Dict[str, Any]:
        """Initiate graceful shutdown via IPC (STORY-3.3 SIGTERM channel).

        Unlike SIGTERM/SIGINT, this:
          - Returns synchronous ACK to the caller with current state
          - Persists the reason to context bus for audit
          - Marks the daemon as draining (refuses new tasks)
          - Triggers full graceful shutdown

        Atomic guarantee: the caller receives the ACK only after the daemon
        has flipped its state to draining (action_run_task will now refuse).
        """
        if self.shutting_down:
            return {
                "status": "success",
                "state": "draining",
                "message": "Daemon already shutting down",
                "reason": reason,
            }

        logger.info("Stop requested via IPC. Reason: %s", reason)
        self.shutting_down = True

        # Persist stop event to context bus for audit trail
        try:
            bus_dir = REPO_ROOT / ".agent" / "bus"
            bus_dir.mkdir(parents=True, exist_ok=True)
            import datetime
            stop_event = {
                "id": f"stop_{int(datetime.datetime.utcnow().timestamp())}",
                "type": "daemon_stop",
                "author": "daemon.action_stop",
                "reason": reason,
                "active_tasks_at_stop": list(self.active_tasks.keys()),
                "ts": datetime.datetime.utcnow().isoformat() + "Z",
            }
            bus_file = bus_dir / "daemon_stop.jsonl"
            with open(bus_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(stop_event) + "\n")
        except Exception as e:
            logger.warning("Could not persist stop event to bus: %s", e)

        # Schedule actual shutdown in the background so the caller gets ACK first.
        # We use asyncio.create_task to ensure the response is sent before
        # the server.close() in shutdown() interrupts the connection.
        loop = asyncio.get_running_loop()
        sig = signal.SIGTERM  # Reuse the existing shutdown path
        loop.create_task(self.shutdown(sig))

        return {
            "status": "success",
            "state": "draining",
            "message": "Daemon acknowledged stop; in-flight tasks will finish, new tasks refused",
            "reason": reason,
            "active_tasks_in_flight": list(self.active_tasks.keys()),
        }

    async def shutdown(self, sig: signal.Signals) -> None:
        """Gracefully close sockets and terminate background tasks.

        Idempotent: can be called from a system signal handler OR from the IPC
        action_stop handler. First call wins; subsequent calls only do the
        cleanup that wasn't already done.
        """
        first_call = not self.shutting_down
        self.shutting_down = True
        if first_call:
            logger.info("Received signal %s. Initiating graceful shutdown...", sig.name)
        else:
            logger.info("Shutdown re-entered (via IPC). Continuing cleanup...")

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
