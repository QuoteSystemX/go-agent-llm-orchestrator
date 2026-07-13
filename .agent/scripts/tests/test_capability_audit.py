#!/usr/bin/env python3
"""Tests for STORY-4 capability_audit.py."""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / ".agent" / "scripts" / "dev" / "capability_audit.py"

_spec = importlib.util.spec_from_file_location("capability_audit", str(SCRIPT))
mod = importlib.util.module_from_spec(_spec)
sys.modules["capability_audit"] = _spec.loader
_spec.loader.exec_module(mod)


def make_matrix(tmp: Path, **overrides) -> Path:
    base = {
        "version": "1.0.0",
        "roles": {
            "infra-agent": {
                "capabilities": [
                    {"cap": "modify-tasks", "scope": "global"},
                    {"cap": "stop-daemon", "scope": "global"},
                ]
            },
            "session-agent": {"capabilities": []},
            "squad-agent": {
                "capabilities": [{"cap": "modify-tasks", "scope": "global"}]
            },
            "human": {"capabilities": []},
        },
        "operations": {
            "task_write": "modify-tasks",
            "task_read": "read-tasks",
            "daemon_stop": "stop-daemon",
            "distill": "trigger-distill",
        },
    }
    base.update(overrides)
    p = tmp / "capabilities.yaml"
    import yaml
    p.write_text(yaml.safe_dump(base, allow_unicode=True), encoding="utf-8")
    return p


@pytest.fixture
def fake_matrix(tmp_path, monkeypatch):
    """Override MATRIX_PATH to a per-test directory."""
    p = make_matrix(tmp_path)
    monkeypatch.setattr(mod, "MATRIX_PATH", p)
    return p


class TestSchema:
    def test_valid(self, fake_matrix):
        issues = mod.check_schema({"version": "1.0.0", "roles": {}, "operations": {}})
        assert issues == []

    def test_missing_version(self, fake_matrix):
        issues = mod.check_schema({"roles": {}, "operations": {}})
        assert any("version" in i for i in issues)

    def test_wrong_version(self, fake_matrix):
        issues = mod.check_schema({"version": "99.0.0", "roles": {}, "operations": {}})
        assert any("unsupported version" in i for i in issues)

    def test_missing_roles(self, fake_matrix):
        issues = mod.check_schema({"version": "1.0.0", "operations": {}})
        assert any("roles" in i for i in issues)


class TestDefaultDeny:
    def test_empty_session_agent_ok(self, fake_matrix):
        matrix = {
            "version": "1.0.0",
            "roles": {"session-agent": {"capabilities": []}},
            "operations": {},
        }
        issues = mod.check_default_deny(matrix)
        assert issues == []

    def test_session_agent_with_caps_violation(self, fake_matrix):
        matrix = {
            "version": "1.0.0",
            "roles": {
                "session-agent": {
                    "capabilities": [{"cap": "modify-tasks", "scope": "global"}]
                }
            },
            "operations": {},
        }
        issues = mod.check_default_deny(matrix)
        assert len(issues) == 1
        assert "default-deny" in issues[0]
        assert "modify-tasks" in issues[0]


class TestRequiredOperations:
    def test_all_present(self, fake_matrix):
        matrix = {
            "version": "1.0.0",
            "roles": {},
            "operations": {
                "task_write": "modify-tasks",
                "task_read": "read-tasks",
                "daemon_start": "start-daemon",
                "daemon_stop": "stop-daemon",
                "distill": "trigger-distill",
                "infra_write": "modify-infra",
                "infra_read": "read-infra",
                "harness_run": "harness-run",
                "config_write": "modify-config",
                "bus_read": "read-bus",
                "bus_write": "modify-bus",
            },
        }
        issues = mod.check_required_operations(matrix)
        assert issues == []

    def test_missing_op(self, fake_matrix):
        matrix = {
            "version": "1.0.0",
            "roles": {},
            "operations": {},  # missing everything
        }
        issues = mod.check_required_operations(matrix)
        assert len(issues) == len(mod.REQUIRED_OPERATIONS)
        assert any("daemon_stop" in i for i in issues)

    def test_wrong_mapping(self, fake_matrix):
        matrix = {
            "version": "1.0.0",
            "roles": {},
            "operations": {
                "task_write": "wrong-cap",  # wrong
            },
        }
        issues = mod.check_required_operations(matrix)
        assert any("wrong-cap" in i for i in issues)


class TestCapDrift:
    def test_clean(self, fake_matrix):
        matrix = {
            "version": "1.0.0",
            "roles": {
                "infra-agent": {
                    "capabilities": [{"cap": "modify-tasks", "scope": "global"}]
                }
            },
            "operations": {"task_write": "modify-tasks"},
        }
        issues = mod.check_cap_drift(matrix)
        assert issues == []

    def test_dead_caps_detected(self, fake_matrix):
        matrix = {
            "version": "1.0.0",
            "roles": {
                "infra-agent": {
                    "capabilities": [
                        {"cap": "modify-tasks", "scope": "global"},
                        {"cap": "obsolete-cap", "scope": "global"},
                    ]
                }
            },
            "operations": {"task_write": "modify-tasks"},
        }
        issues = mod.check_cap_drift(matrix)
        assert any("obsolete-cap" in i for i in issues)

    def test_invalid_cap_name(self, fake_matrix):
        matrix = {
            "version": "1.0.0",
            "roles": {},
            "operations": {"task_write": "bad@char!cap"},
        }
        issues = mod.check_cap_drift(matrix)
        assert any("invalid cap name" in i for i in issues)


class TestWildcards:
    def test_clean(self, fake_matrix):
        matrix = {
            "version": "1.0.0",
            "roles": {
                "squad-agent": {
                    "capabilities": [{"cap": "modify-tasks", "scope": "global"}]
                }
            },
            "operations": {},
        }
        warnings = mod.check_wildcards(matrix)
        assert warnings == []

    def test_proper_wildcard_ok(self, fake_matrix):
        matrix = {
            "version": "1.0.0",
            "roles": {
                "squad-agent": {
                    "capabilities": [{"cap": "modify-tasks", "scope": "task:*"}]
                }
            },
            "operations": {},
        }
        warnings = mod.check_wildcards(matrix)
        assert warnings == []

    def test_literal_star_in_quotes_ok(self, fake_matrix):
        """Scope: task:"*" is a literal "*" in quotes, not a wildcard."""
        matrix = {
            "version": "1.0.0",
            "roles": {
                "squad-agent": {
                    "capabilities": [{"cap": "modify-tasks", "scope": 'task:"*"'}]
                }
            },
            "operations": {},
        }
        warnings = mod.check_wildcards(matrix)
        assert warnings == []

    def test_unusual_wildcard_flagged(self, fake_matrix):
        matrix = {
            "version": "1.0.0",
            "roles": {
                "squad-agent": {
                    "capabilities": [{"cap": "modify-tasks", "scope": "task*"}]
                }
            },
            "operations": {},
        }
        warnings = mod.check_wildcards(matrix)
        assert len(warnings) == 1
        assert "unusual wildcard" in warnings[0]


class TestConstraints:
    def test_clean(self, fake_matrix):
        matrix = {
            "version": "1.0.0",
            "roles": {
                "infra-agent": {
                    "capabilities": [
                        {
                            "cap": "harness-run",
                            "scope": "global",
                            "constraint": "manifest_required",
                        }
                    ]
                }
            },
            "operations": {},
        }
        issues = mod.check_constraints(matrix)
        assert issues == []

    def test_sensitive_cap_without_constraint(self, fake_matrix):
        matrix = {
            "version": "1.0.0",
            "roles": {
                "infra-agent": {
                    "capabilities": [
                        {"cap": "harness-run", "scope": "global"}  # no constraint
                    ]
                }
            },
            "operations": {},
        }
        issues = mod.check_constraints(matrix)
        assert any("harness-run" in i for i in issues)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
