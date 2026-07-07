#!/usr/bin/env python3
"""SQLite database layer for the agent orchestrator daemon."""

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parents[4] / ".agent" / "bus" / "orchestrator.db"


class DaemonDB:
    """Manages SQLite connection in WAL mode and handles orchestrator state persistence."""

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for high concurrency
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            # Table for Task State
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    issue_description TEXT NOT NULL,
                    adr_document TEXT,
                    subtasks TEXT, -- JSON array
                    current_files TEXT, -- JSON object
                    git_diff TEXT,
                    test_results TEXT, -- JSON object
                    trace_path TEXT, -- JSON array
                    active_node TEXT NOT NULL DEFAULT 'cto',
                    status TEXT NOT NULL DEFAULT 'planning',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            # Table for Agent Nodes cache
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_nodes (
                    name TEXT PRIMARY KEY,
                    description TEXT,
                    reports_to TEXT,
                    delegates_to TEXT, -- JSON array
                    domains TEXT, -- JSON array
                    tools TEXT -- JSON array
                )
                """
            )

            # Table for Execution Traces / History
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS execution_traces (
                    session_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    traversal_path TEXT NOT NULL, -- JSON array
                    llm_calls TEXT NOT NULL, -- JSON array
                    verification_attempts TEXT NOT NULL, -- JSON array
                    final_status TEXT NOT NULL,
                    total_elapsed_seconds REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (task_id) REFERENCES tasks (id) ON DELETE CASCADE
                )
                """
            )

            # Table for Workspace Locks (Idempotency and concurrency safety)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS locks (
                    name TEXT PRIMARY KEY,
                    holder TEXT NOT NULL,
                    expires_at REAL NOT NULL -- unix epoch float
                )
                """
            )
            conn.commit()

    # --- Task Operations ---

    def save_task(self, task_id: str, state_dict: Dict[str, Any]) -> None:
        """Insert or replace a task state record."""
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO tasks (
                    id, issue_description, adr_document, subtasks,
                    current_files, git_diff, test_results, trace_path,
                    active_node, status, updated_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP
                )
                """,
                (
                    task_id,
                    state_dict.get("issue_description", ""),
                    state_dict.get("adr_document"),
                    json.dumps(state_dict.get("subtasks", [])),
                    json.dumps(state_dict.get("current_files", {})),
                    state_dict.get("git_diff"),
                    json.dumps(state_dict.get("test_results")),
                    json.dumps(state_dict.get("trace_path", [])),
                    state_dict.get("active_node", "cto"),
                    state_dict.get("status", "planning"),
                ),
            )
            conn.commit()

    def load_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Load a task state by ID, parsing JSON fields back into Python structures."""
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if not row:
                return None
            
            d = dict(row)
            return {
                "issue_description": d["issue_description"],
                "adr_document": d["adr_document"],
                "subtasks": json.loads(d["subtasks"] or "[]"),
                "current_files": json.loads(d["current_files"] or "{}"),
                "git_diff": d["git_diff"],
                "test_results": json.loads(d["test_results"] or "null"),
                "trace_path": json.loads(d["trace_path"] or "[]"),
                "active_node": d["active_node"],
                "status": d["status"],
            }

    # --- Agent Node Operations ---

    def cache_nodes(self, nodes: List[Any]) -> None:
        """Cache all scanned AgentNodes into SQLite."""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM agent_nodes")
            for node in nodes:
                conn.execute(
                    """
                    INSERT INTO agent_nodes (
                        name, description, reports_to, delegates_to, domains, tools
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        node.name,
                        node.description,
                        node.reports_to,
                        json.dumps(node.delegates_to),
                        json.dumps(node.domains),
                        json.dumps(node.tools),
                    ),
                )
            conn.commit()

    def get_cached_nodes(self) -> Dict[str, Any]:
        """Load cached AgentNodes from SQLite."""
        with self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM agent_nodes").fetchall()
            nodes_dict = {}
            for row in rows:
                d = dict(row)
                nodes_dict[d["name"]] = {
                    "name": d["name"],
                    "description": d["description"],
                    "reports_to": d["reports_to"],
                    "delegates_to": json.loads(d["delegates_to"] or "[]"),
                    "domains": json.loads(d["domains"] or "[]"),
                    "tools": json.loads(d["tools"] or "[]"),
                }
            return nodes_dict

    # --- Locks Operations ---

    def acquire_lock(self, name: str, holder: str, ttl_seconds: float = 600.0) -> bool:
        """
        Attempt to acquire a workspace lock.
        Returns True if successful, False if already locked by someone else.
        """
        import time
        now = time.time()
        expires_at = now + ttl_seconds
        
        with self._get_conn() as conn:
            # Clean expired locks first
            conn.execute("DELETE FROM locks WHERE expires_at < ?", (now,))
            
            try:
                conn.execute(
                    "INSERT INTO locks (name, holder, expires_at) VALUES (?, ?, ?)",
                    (name, holder, expires_at),
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                # Lock is already held
                row = conn.execute("SELECT holder, expires_at FROM locks WHERE name = ?", (name,)).fetchone()
                if row:
                    logger.debug("Lock '%s' held by '%s' until %s", name, row["holder"], row["expires_at"])
                return False

    def release_lock(self, name: str, holder: str) -> None:
        """Release the workspace lock if held by the specified holder."""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM locks WHERE name = ? AND holder = ?", (name, holder))
            conn.commit()

    # --- Trace Operations ---

    def save_trace(self, session_id: str, task_id: str, trace_dict: Dict[str, Any]) -> None:
        """Save a completed squad execution trace."""
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO execution_traces (
                    session_id, task_id, traversal_path, llm_calls,
                    verification_attempts, final_status, total_elapsed_seconds
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    task_id,
                    json.dumps(trace_dict.get("traversal_path", [])),
                    json.dumps(trace_dict.get("llm_calls", [])),
                    json.dumps(trace_dict.get("verification_attempts", [])),
                    trace_dict.get("final_status", "unknown"),
                    trace_dict.get("total_elapsed_seconds", 0.0),
                ),
            )
            conn.commit()
