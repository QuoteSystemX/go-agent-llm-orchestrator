#!/usr/bin/env python3
"""Pydantic schemas for the squad orchestration system."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / ".agent" / "scripts"))

from lib.common import load_json_safe, save_json_atomic  # noqa: E402

BUS_DIR = REPO_ROOT / ".agent" / "bus"


class AgentNode(BaseModel):
    name: str
    description: str = ""
    reports_to: Optional[str] = None
    delegates_to: List[str] = Field(default_factory=list)
    domains: List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)


class HierarchyGraph(BaseModel):
    nodes: Dict[str, AgentNode] = Field(default_factory=dict)

    def validate_integrity(self) -> None:
        """Check for unknown delegates and dependency cycles (DFS)."""
        for name, node in self.nodes.items():
            for delegate in node.delegates_to:
                if delegate not in self.nodes:
                    raise ValueError(
                        f"Agent '{name}' delegates to unknown agent '{delegate}'"
                    )

        WHITE, GRAY, BLACK = 0, 1, 2
        color: Dict[str, int] = {n: WHITE for n in self.nodes}

        def _dfs(node_name: str) -> None:
            color[node_name] = GRAY
            for neighbor in self.nodes[node_name].delegates_to:
                if color.get(neighbor) == GRAY:
                    raise ValueError(
                        f"Cycle detected: '{node_name}' -> '{neighbor}'"
                    )
                if color.get(neighbor) == WHITE:
                    _dfs(neighbor)
            color[node_name] = BLACK

        for name in list(self.nodes):
            if color[name] == WHITE:
                _dfs(name)


class TaskState(BaseModel):
    issue_description: str
    adr_document: Optional[str] = None
    subtasks: List[Dict[str, str]] = Field(default_factory=list)
    current_files: Dict[str, str] = Field(default_factory=dict)
    git_diff: Optional[str] = None
    test_results: Optional[Dict[str, Any]] = None
    trace_path: List[str] = Field(default_factory=list)
    active_node: str = "cto"
    status: str = "planning"  # planning | executing | testing | completed | failed

    def save(self, path: Optional[Path] = None) -> bool:
        dest = path or (BUS_DIR / "task_state.json")
        return save_json_atomic(dest, self.model_dump())

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "TaskState":
        src = path or (BUS_DIR / "task_state.json")
        data = load_json_safe(src)
        if not data:
            raise FileNotFoundError(f"No task state found at {src}")
        return cls(**data)
