#!/usr/bin/env python3
"""
Tests for STORY-4 capability_check (default-deny).

Covers:
  - load_matrix: loads valid YAML
  - load_matrix: rejects unsupported version
  - load_matrix: rejects missing file
  - load_matrix: rejects invalid schema
  - check: default-deny (unknown role)
  - check: default-deny (unknown operation)
  - check: session-agent is empty (everything denied)
  - check: infra-agent allowed for most ops
  - check: squad-agent NOT allowed to modify-infra
  - check: scope matching (global covers everything)
  - check: scope matching (repo:foo only matches repo:foo)
  - check: wildcard task:* matches any task
"""
import importlib.util
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / ".agent" / "scripts" / "permissions" / "capability_check.py"

_spec = importlib.util.spec_from_file_location("capability_check", str(SCRIPT))
mod = importlib.util.module_from_spec(_spec)
sys.modules["capability_check"] = mod
_spec.loader.exec_module(mod)


VALID_YAML = """
version: "1.0.0"
roles:
  infra-agent:
    capabilities:
      - { cap: modify-bus, scope: global }
      - { cap: modify-infra, scope: global }
  squad-agent:
    capabilities:
      - { cap: read-bus, scope: global }
  session-agent:
    capabilities: []
  human:
    capabilities:
      - { cap: read-bus, scope: global }
operations:
  bus_write: modify-bus
  bus_read: read-bus
  infra_write: modify-infra
"""


@pytest.fixture
def matrix_file(tmp_path):
    p = tmp_path / "caps.yaml"
    p.write_text(VALID_YAML, encoding="utf-8")
    return p


class TestLoadMatrix:
    def test_loads_valid(self, matrix_file):
        m = mod.load_matrix(matrix_file)
        assert m["version"] == "1.0.0"
        assert "infra-agent" in m["roles"]
        assert m["operations"]["bus_write"] == "modify-bus"

    def test_unsupported_version(self, tmp_path):
        p = tmp_path / "caps.yaml"
        p.write_text('version: "99.0.0"\nroles: {}\noperations: {}', encoding="utf-8")
        with pytest.raises(ValueError, match="Unsupported"):
            mod.load_matrix(p)

    def test_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            mod.load_matrix(tmp_path / "nope.yaml")

    def test_missing_roles(self, tmp_path):
        p = tmp_path / "caps.yaml"
        p.write_text('version: "1.0.0"\noperations: {}', encoding="utf-8")
        with pytest.raises(ValueError, match="roles"):
            mod.load_matrix(p)


class TestCheckDefaultDeny:
    def test_unknown_role_denied(self, matrix_file):
        m = mod.load_matrix(matrix_file)
        assert mod.check(m, "no-such-role", "bus_read") is False

    def test_unknown_operation_denied(self, matrix_file):
        m = mod.load_matrix(matrix_file)
        assert mod.check(m, "infra-agent", "no-such-op") is False

    def test_session_agent_denied_everything(self, matrix_file):
        m = mod.load_matrix(matrix_file)
        # Even bus_read is denied — session-agent has empty capabilities
        assert mod.check(m, "session-agent", "bus_read") is False
        assert mod.check(m, "session-agent", "bus_write") is False
        assert mod.check(m, "session-agent", "infra_write") is False

    def test_human_denied_infra_write(self, matrix_file):
        m = mod.load_matrix(matrix_file)
        assert mod.check(m, "human", "infra_write") is False
        assert mod.check(m, "human", "bus_write") is False

    def test_squad_agent_denied_infra_write(self, matrix_file):
        m = mod.load_matrix(matrix_file)
        assert mod.check(m, "squad-agent", "infra_write") is False


class TestCheckAllowed:
    def test_infra_agent_bus_write(self, matrix_file):
        m = mod.load_matrix(matrix_file)
        assert mod.check(m, "infra-agent", "bus_write") is True

    def test_infra_agent_infra_write(self, matrix_file):
        m = mod.load_matrix(matrix_file)
        assert mod.check(m, "infra-agent", "infra_write") is True

    def test_squad_agent_bus_read(self, matrix_file):
        m = mod.load_matrix(matrix_file)
        assert mod.check(m, "squad-agent", "bus_read") is True

    def test_human_bus_read(self, matrix_file):
        m = mod.load_matrix(matrix_file)
        assert mod.check(m, "human", "bus_read") is True


class TestScopeMatching:
    def test_global_covers_anything(self, matrix_file):
        m = mod.load_matrix(matrix_file)
        assert mod.check(m, "infra-agent", "bus_write", scope="repo:foo") is True
        assert mod.check(m, "infra-agent", "bus_write", scope="task:abc") is True

    def test_explicit_scope_must_match(self, tmp_path):
        p = tmp_path / "caps.yaml"
        p.write_text("""
version: "1.0.0"
roles:
  scoped-agent:
    capabilities:
      - { cap: modify-bus, scope: "repo:foo" }
operations:
  bus_write: modify-bus
""", encoding="utf-8")
        m = mod.load_matrix(p)
        assert mod.check(m, "scoped-agent", "bus_write", scope="repo:foo") is True
        assert mod.check(m, "scoped-agent", "bus_write", scope="repo:bar") is False
        assert mod.check(m, "scoped-agent", "bus_write", scope="global") is False

    def test_wildcard_scope(self, tmp_path):
        p = tmp_path / "caps.yaml"
        p.write_text("""
version: "1.0.0"
roles:
  wildcard-agent:
    capabilities:
      - { cap: modify-tasks, scope: "task:*" }
operations:
  task_write: modify-tasks
""", encoding="utf-8")
        m = mod.load_matrix(p)
        assert mod.check(m, "wildcard-agent", "task_write", scope="task:abc") is True
        assert mod.check(m, "wildcard-agent", "task_write", scope="task:xyz") is True
        assert mod.check(m, "wildcard-agent", "task_write", scope="repo:foo") is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
