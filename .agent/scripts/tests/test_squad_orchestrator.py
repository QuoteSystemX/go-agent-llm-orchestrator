#!/usr/bin/env python3
"""Unit tests for squad_orchestrator and squad_schemas."""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(REPO_ROOT / ".agent" / "scripts"))

from orchestration.squad_schemas import AgentNode, HierarchyGraph, TaskState
from orchestration.squad_orchestrator import (
    AgentScanner,
    GraphBuilder,
    ToolSandbox,
    ExecutionEngine,
    check_output_guardrails,
    MANAGEMENT_ROLES,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _make_agent_md(name: str, domains: list[str], delegates_to: list[str]) -> str:
    delegates = "\n".join(f"    - {d}" for d in delegates_to)
    delegate_block = f"  delegates_to:\n{delegates}" if delegates_to else "  delegates_to: []"
    return f"""---
name: {name}
description: Test agent {name}
hierarchy:
  reports_to: null
  {delegate_block.strip()}
domains: {", ".join(domains)}
tools: Read, Grep
---

# {name}

Body text.
"""


# ─── AgentScanner ─────────────────────────────────────────────────────────────

class TestAgentScanner(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.agents_dir = self.tmp / "agents"
        self.agents_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, filename: str, content: str) -> None:
        (self.agents_dir / filename).write_text(content, encoding="utf-8")

    def test_parses_frontmatter_fields(self):
        self._write("alpha.md", _make_agent_md("alpha", ["backend", "go"], ["beta"]))
        self._write("beta.md", _make_agent_md("beta", ["test"], []))

        scanner = AgentScanner()
        nodes = scanner.scan(agents_dir=self.agents_dir)

        self.assertEqual(len(nodes), 2)
        alpha = next(n for n in nodes if n.name == "alpha")
        self.assertIn("backend", alpha.domains)
        self.assertIn("go", alpha.domains)
        self.assertEqual(alpha.delegates_to, ["beta"])

    def test_skips_files_without_frontmatter(self):
        self._write("no_fm.md", "# Just a heading\n\nNo frontmatter here.\n")
        scanner = AgentScanner()
        nodes = scanner.scan(agents_dir=self.agents_dir)
        self.assertEqual(len(nodes), 0)

    def test_skips_files_without_name(self):
        self._write("nameless.md", "---\ndescription: test\n---\nBody\n")
        scanner = AgentScanner()
        nodes = scanner.scan(agents_dir=self.agents_dir)
        self.assertEqual(len(nodes), 0)

    def test_scans_subdirectories(self):
        sub = self.agents_dir / "core"
        sub.mkdir()
        (sub / "x.md").write_text(_make_agent_md("x", ["infra"], []), encoding="utf-8")
        scanner = AgentScanner()
        nodes = scanner.scan(agents_dir=self.agents_dir)
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].name, "x")


# ─── GraphBuilder / HierarchyGraph ────────────────────────────────────────────

class TestGraphCycleDetection(unittest.TestCase):
    def _graph(self, edges: dict[str, list[str]]) -> HierarchyGraph:
        nodes = {
            name: AgentNode(name=name, delegates_to=dests)
            for name, dests in edges.items()
        }
        return HierarchyGraph(nodes=nodes)

    def test_valid_dag_passes(self):
        g = self._graph({"a": ["b"], "b": ["c"], "c": []})
        g.validate_integrity()  # should not raise

    def test_direct_cycle_raises(self):
        g = self._graph({"a": ["b"], "b": ["a"]})
        with self.assertRaises(ValueError):
            g.validate_integrity()

    def test_indirect_cycle_raises(self):
        g = self._graph({"a": ["b"], "b": ["c"], "c": ["a"]})
        with self.assertRaises(ValueError):
            g.validate_integrity()

    def test_unknown_delegate_raises(self):
        g = self._graph({"a": ["ghost"]})
        with self.assertRaises(ValueError):
            g.validate_integrity()


# ─── ToolSandbox ──────────────────────────────────────────────────────────────

class TestToolSandboxEnforcement(unittest.TestCase):
    def test_management_role_blocks_write_file(self):
        sandbox = ToolSandbox("cto")
        with self.assertRaises(PermissionError):
            sandbox.check("write_file")

    def test_management_role_blocks_bash(self):
        sandbox = ToolSandbox("reviewer")
        with self.assertRaises(PermissionError):
            sandbox.check("Bash")

    def test_specialist_role_allows_write(self):
        sandbox = ToolSandbox("go-specialist")
        sandbox.check("write_file")  # must not raise

    def test_filter_removes_forbidden_tools(self):
        sandbox = ToolSandbox("backend-lead")
        tools = ["Read", "Grep", "Write", "Bash", "Edit"]
        allowed = sandbox.filter_tools(tools)
        self.assertNotIn("Write", allowed)
        self.assertNotIn("Bash", allowed)
        self.assertNotIn("Edit", allowed)
        self.assertIn("Read", allowed)

    def test_filter_preserves_all_for_specialists(self):
        sandbox = ToolSandbox("go-specialist")
        tools = ["Read", "Write", "Bash"]
        self.assertEqual(sandbox.filter_tools(tools), tools)


# ─── Output Guardrails ────────────────────────────────────────────────────────

class TestOutputGuardrails(unittest.TestCase):
    def test_code_block_in_management_response_fails(self):
        ok, _ = check_output_guardrails("cto", "Here is the plan:\n```python\nprint('hi')\n```")
        self.assertFalse(ok)

    def test_prose_in_management_response_passes(self):
        ok, _ = check_output_guardrails("cto", "Delegate to backend-lead for implementation.")
        self.assertTrue(ok)

    def test_code_block_in_specialist_response_passes(self):
        ok, _ = check_output_guardrails("go-specialist", "```go\nfmt.Println('hi')\n```")
        self.assertTrue(ok)


# ─── ExecutionEngine — dynamic routing ────────────────────────────────────────

class TestDynamicRouting(unittest.TestCase):
    def _build_graph(self) -> HierarchyGraph:
        nodes = {
            "cto": AgentNode(
                name="cto",
                domains=["strategy"],
                delegates_to=["backend-lead"],
            ),
            "backend-lead": AgentNode(
                name="backend-lead",
                domains=["backend", "go"],
                delegates_to=["go-specialist", "test-engineer"],
            ),
            "go-specialist": AgentNode(name="go-specialist", domains=["go"], delegates_to=[]),
            "test-engineer": AgentNode(name="test-engineer", domains=["test"], delegates_to=[]),
        }
        return HierarchyGraph(nodes=nodes)

    @patch("orchestration.squad_orchestrator.query_llm_safe")
    @patch("orchestration.squad_orchestrator.subprocess.run")
    def test_routes_to_lead_on_domain_match(self, mock_run, mock_llm):
        mock_llm.return_value = ("backend-lead", "stub", {"model": "test"})
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")

        graph = self._build_graph()
        state = TaskState(issue_description="implement REST API endpoint in Go")
        engine = ExecutionEngine(graph, dry_run=False)

        with patch.object(engine, "_decompose_task", return_value=[
            {"agent": "go-specialist", "task": "implement"},
            {"agent": "test-engineer", "task": "test"},
        ]):
            final = engine.run(state)

        self.assertIn("cto", final.trace_path)
        self.assertIn("backend-lead", final.trace_path)


# ─── ExecutionEngine — self-healing ───────────────────────────────────────────

class TestVerificationRetrySuccess(unittest.TestCase):
    def _build_graph(self) -> HierarchyGraph:
        nodes = {
            "cto": AgentNode(name="cto", domains=["strategy"], delegates_to=["backend-lead"]),
            "backend-lead": AgentNode(name="backend-lead", domains=["backend"], delegates_to=["go-specialist", "test-engineer"]),
            "go-specialist": AgentNode(name="go-specialist", domains=["go"], delegates_to=[]),
            "test-engineer": AgentNode(name="test-engineer", domains=["test"], delegates_to=[]),
        }
        return HierarchyGraph(nodes=nodes)

    @patch("orchestration.squad_orchestrator.query_llm_safe")
    @patch("orchestration.squad_orchestrator.subprocess.run")
    def test_succeeds_on_second_attempt(self, mock_run, mock_llm):
        mock_llm.return_value = ("backend-lead", "stub", {"model": "test"})

        # First go test call fails, second succeeds
        mock_run.side_effect = [
            MagicMock(returncode=1, stdout="FAIL", stderr="compile error"),
            MagicMock(returncode=0, stdout="ok", stderr=""),
        ]

        graph = self._build_graph()
        state = TaskState(issue_description="fix a bug")
        engine = ExecutionEngine(graph, dry_run=False)

        with patch.object(engine, "_pick_lead", return_value="backend-lead"), \
             patch.object(engine, "_decompose_task", return_value=[
                 {"agent": "go-specialist", "task": "fix"},
                 {"agent": "test-engineer", "task": "test"},
             ]):
            final = engine.run(state)

        # Status must be completed
        self.assertEqual(final.status, "completed")
        # Exactly 2 verification attempts: 1 fail + 1 success
        self.assertEqual(len(engine._trace["verification_attempts"]), 2)
        self.assertFalse(engine._trace["verification_attempts"][0]["success"])
        self.assertTrue(engine._trace["verification_attempts"][1]["success"])
        # go-specialist must appear in traversal_path after the initial delegation
        # (first as developer, then as self-heal target)
        go_visits = [n for n in final.trace_path if n == "go-specialist"]
        self.assertGreaterEqual(len(go_visits), 2,
            "go-specialist should be visited at least twice: initial run + self-heal re-send")


class TestVerificationRetryExhausted(unittest.TestCase):
    def _build_graph(self) -> HierarchyGraph:
        nodes = {
            "cto": AgentNode(name="cto", domains=["strategy"], delegates_to=["backend-lead"]),
            "backend-lead": AgentNode(name="backend-lead", domains=["backend"], delegates_to=["go-specialist", "test-engineer"]),
            "go-specialist": AgentNode(name="go-specialist", domains=["go"], delegates_to=[]),
            "test-engineer": AgentNode(name="test-engineer", domains=["test"], delegates_to=[]),
        }
        return HierarchyGraph(nodes=nodes)

    @patch("orchestration.squad_orchestrator.query_llm_safe")
    @patch("orchestration.squad_orchestrator.subprocess.run")
    def test_fails_after_max_retries(self, mock_run, mock_llm):
        mock_llm.return_value = ("fallback response", "stub", {"model": "test"})
        mock_run.return_value = MagicMock(returncode=1, stdout="FAIL", stderr="persistent error")

        graph = self._build_graph()
        state = TaskState(issue_description="impossible task")
        engine = ExecutionEngine(graph, dry_run=False)

        with patch.object(engine, "_pick_lead", return_value="backend-lead"), \
             patch.object(engine, "_decompose_task", return_value=[
                 {"agent": "go-specialist", "task": "implement"},
                 {"agent": "test-engineer", "task": "test"},
             ]):
            final = engine.run(state)

        self.assertEqual(final.status, "failed")
        self.assertEqual(len(engine._trace["verification_attempts"]), 3)
        self.assertFalse(all(a["success"] for a in engine._trace["verification_attempts"]))
        self.assertIn("last_errors", final.test_results)


# ─── TaskState persistence ────────────────────────────────────────────────────

class TestTaskStatePersistence(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_save_and_load_roundtrip(self):
        state = TaskState(
            issue_description="test task",
            status="executing",
            active_node="go-specialist",
            trace_path=["cto", "backend-lead", "go-specialist"],
        )
        path = self.tmp / "state.json"
        ok = state.save(path)
        self.assertTrue(ok)

        loaded = TaskState.load(path)
        self.assertEqual(loaded.issue_description, state.issue_description)
        self.assertEqual(loaded.status, state.status)
        self.assertEqual(loaded.trace_path, state.trace_path)


class TestTreeAutoHeal(unittest.TestCase):
    def _build_graph(self) -> HierarchyGraph:
        nodes = {
            "cto": AgentNode(name="cto", domains=["strategy"], delegates_to=["backend-lead"]),
            "backend-lead": AgentNode(name="backend-lead", domains=["backend"], delegates_to=["go-specialist", "test-engineer"]),
            "go-specialist": AgentNode(name="go-specialist", domains=["go"], delegates_to=[]),
            "test-engineer": AgentNode(name="test-engineer", domains=["test"], delegates_to=[]),
        }
        return HierarchyGraph(nodes=nodes)

    @patch("orchestration.squad_orchestrator.query_llm_safe")
    @patch("analysis.ghost_prototyper.run_isolated_worktree", return_value=(True, {}))
    @patch("orchestration.squad_orchestrator.subprocess.run")
    def test_tree_auto_heal_success(self, mock_run, mock_worktree, mock_llm):
        mock_llm.side_effect = [
            ("backend-lead", "stub", {"model": "test"}),
            ("implemented", "stub", {"model": "test"}),
            ("tested", "stub", {"model": "test"}),
            ('[{"intent": "fix nil check", "file": "main.go", "target": "nil", "replacement": "not nil"}]', "stub", {"model": "test"})
        ]
        
        mock_run.side_effect = [
            MagicMock(returncode=1, stdout="FAIL", stderr="nil pointer"),
            MagicMock(returncode=0, stdout="ok", stderr="")
        ]

        graph = self._build_graph()
        state = TaskState(issue_description="fix a bug")
        engine = ExecutionEngine(graph, dry_run=False)

        with patch.object(engine, "_decompose_task", return_value=[
                  {"agent": "go-specialist", "task": "fix"},
                  {"agent": "test-engineer", "task": "test"},
              ]):
            final = engine.run(state)

        self.assertEqual(final.status, "completed")
        self.assertEqual(len(engine._trace["verification_attempts"]), 2)

    @patch("orchestration.squad_orchestrator.query_llm_safe")
    @patch("analysis.ghost_prototyper.run_isolated_worktree", return_value=(True, {}))
    @patch("orchestration.squad_orchestrator.subprocess.run")
    def test_tree_auto_heal_skips_dead_end(self, mock_run, mock_worktree, mock_llm):
        graph = self._build_graph()
        engine = ExecutionEngine(graph, dry_run=False)
        state = TaskState(issue_description="fix a bug")

        from orchestration.dead_ends import log_dead_end, clear_dead_ends
        clear_dead_ends()
        log_dead_end("main.go", "Replace:\nnil\nWith:\nnot nil", "compile error")

        mock_llm.side_effect = [
            ('[{"intent": "fix nil check", "file": "main.go", "target": "nil", "replacement": "not nil"}]', "stub", {"model": "test"})
        ]
        
        success, winning_intent = engine._tree_auto_heal(state, "go-specialist", "test failed")
        
        self.assertFalse(success)
        self.assertIsNone(winning_intent)
        mock_worktree.assert_not_called()
        clear_dead_ends()

    @patch("orchestration.squad_orchestrator.query_llm_safe")
    @patch("analysis.ghost_prototyper.run_isolated_worktree")
    @patch("orchestration.squad_orchestrator.subprocess.run")
    def test_tree_auto_heal_benchmark_selection(self, mock_run, mock_worktree, mock_llm):
        graph = self._build_graph()
        engine = ExecutionEngine(graph, dry_run=False)
        state = TaskState(issue_description="optimize bench performance")

        # Two candidate hypotheses
        mock_llm.side_effect = [
            ('[{"intent": "candidate 1 - slow", "file": "main.go", "target": "slow", "replacement": "less slow"},'
             '{"intent": "candidate 2 - fast", "file": "main.go", "target": "slow", "replacement": "super fast"}]',
             "stub", {"model": "test"})
        ]

        # The baseline run and the candidate runs
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="BenchmarkFoo-8 100 200 ns/op 100 B/op 4 allocs/op", stderr="")
        ]

        # mock_worktree yields metrics for both candidates.
        # Candidate 1 (slow): ns_op=150, allocs=3
        # Candidate 2 (fast): ns_op=80, allocs=1
        mock_worktree.side_effect = [
            (True, {"ns_op": 150.0, "b_op": 50.0, "allocs_op": 3.0, "count": 1}),
            (True, {"ns_op": 80.0, "b_op": 20.0, "allocs_op": 1.0, "count": 1}),
        ]

        success, winning_intent = engine._tree_auto_heal(state, "go-specialist", "bench failed")

        self.assertTrue(success)
        self.assertEqual(winning_intent, "candidate 2 - fast")


if __name__ == "__main__":
    unittest.main(verbosity=2)
