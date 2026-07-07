#!/usr/bin/env python3
import unittest
import sys
from pathlib import Path

# Setup paths
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))
sys.path.append(str(REPO_ROOT / ".agent" / "scripts" / "orchestration"))

from dag_runner import parse_yaml_frontmatter, detect_cycles, translate_path, get_agent_concrete_model

class TestDAGRunner(unittest.TestCase):

    def test_parse_yaml_frontmatter_standard(self):
        content = """---
id: test-task-1
agent: specialists/data/database-architect
dependencies:
  - dep-1
  - dep-2
status: pending
validation:
  - name: Check Schema
    command: python3 check.py
---
Task description text here
"""
        fm, body = parse_yaml_frontmatter(content)
        self.assertEqual(fm.get("id"), "test-task-1")
        self.assertEqual(fm.get("agent"), "specialists/data/database-architect")
        self.assertEqual(fm.get("dependencies"), ["dep-1", "dep-2"])
        self.assertEqual(fm.get("status"), "pending")
        self.assertEqual(len(fm.get("validation", [])), 1)
        self.assertEqual(fm.get("validation")[0]["name"], "Check Schema")
        self.assertEqual(fm.get("validation")[0]["command"], "python3 check.py")
        self.assertEqual(body.strip(), "Task description text here")

    def test_parse_yaml_frontmatter_no_fm(self):
        content = "Just simple text without frontmatter"
        fm, body = parse_yaml_frontmatter(content)
        self.assertEqual(fm, {})
        self.assertEqual(body, content)

    def test_detect_cycles_acyclic(self):
        # A -> B, A -> C, B -> D
        # Graph nodes: D (no deps), B (dep D), C (no deps), A (dep B, C)
        class DummyNode:
            def __init__(self, node_id, deps):
                self.id = node_id
                self.dependencies = deps

        nodes = {
            "A": DummyNode("A", ["B", "C"]),
            "B": DummyNode("B", ["D"]),
            "C": DummyNode("C", []),
            "D": DummyNode("D", [])
        }
        self.assertFalse(detect_cycles(nodes))

    def test_detect_cycles_cyclic(self):
        # A -> B -> C -> A
        class DummyNode:
            def __init__(self, node_id, deps):
                self.id = node_id
                self.dependencies = deps

        nodes = {
            "A": DummyNode("A", ["B"]),
            "B": DummyNode("B", ["C"]),
            "C": DummyNode("C", ["A"])
        }
        self.assertTrue(detect_cycles(nodes))

    def test_translate_path_bus(self):
        run_dir = REPO_ROOT / ".agent" / "bus" / "artifacts" / "run_test_123"
        p = ".agent/bus/artifacts/subfolder/schema.json"
        res = translate_path(p, run_dir)
        self.assertEqual(res, run_dir / "subfolder" / "schema.json")

    def test_translate_path_normal(self):
        run_dir = REPO_ROOT / ".agent" / "bus" / "artifacts" / "run_test_123"
        p = "db/migrations/001.sql"
        res = translate_path(p, run_dir)
        self.assertEqual(res, REPO_ROOT / "db" / "migrations" / "001.sql")

if __name__ == "__main__":
    unittest.main()
