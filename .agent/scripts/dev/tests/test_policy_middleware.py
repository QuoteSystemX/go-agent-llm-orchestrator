#!/usr/bin/env python3
"""Tests for GuardrailPipeline + policy_guardrail.check_inline — AAA pattern."""

import json
import sys
import tempfile
import time
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR.parent))

from dev.guardrail_middleware import GuardrailPipeline, PipelineResult
import health.policy_guardrail as guardrail_mod
from health.policy_guardrail import check_inline


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_rules_cache():
    """Clear module-level cache before each test."""
    guardrail_mod._RULES_CACHE = {}
    guardrail_mod._RULES_MTIME = 0.0
    guardrail_mod._WATCHDOG_MTIME = 0.0
    yield
    guardrail_mod._RULES_CACHE = {}
    guardrail_mod._RULES_MTIME = 0.0
    guardrail_mod._WATCHDOG_MTIME = 0.0


@pytest.fixture()
def rules_file(tmp_path):
    """Write a minimal policy_rules.json and point the module at it."""
    rules = {
        "version": "1.0",
        "categories": [
            {
                "name": "forbidden_commands",
                "severity": "critical",
                "patterns": [
                    {"id": "cmd_rm_rf_root", "regex": "rm\\s+-[rf]+\\s+/(?:\\s|$|[^a-zA-Z])",
                     "description": "Unauthorized root delete", "block_on_match": True},
                ],
            },
            {
                "name": "credential_leak",
                "severity": "critical",
                "patterns": [
                    {"id": "aws_access_key", "regex": "AKIA[0-9A-Z]{16}",
                     "description": "AWS access key in output", "block_on_match": True},
                    {"id": "hardcoded_password",
                     "regex": "password\\s*[:=]\\s*[\"'][^\"'\\s]{4,}[\"']",
                     "description": "Hardcoded password", "block_on_match": True},
                ],
            },
            {
                "name": "hallucination_markers",
                "severity": "medium",
                "patterns": [
                    {"id": "deferred_placeholder",
                     "regex": "TODO:\\s*create this file later",
                     "description": "Deferred placeholder output", "block_on_match": False},
                ],
            },
        ],
    }
    f = tmp_path / "policy_rules.json"
    f.write_text(json.dumps(rules))
    # Patch module-level path resolver
    guardrail_mod._rules_path = lambda: f  # type: ignore[method-assign]
    yield f
    # Restore
    guardrail_mod._rules_path = lambda: (  # type: ignore[method-assign]
        Path(__file__).resolve().parents[4] / ".agent" / "config" / "policy_rules.json"
    )


# ── check_inline ─────────────────────────────────────────────────────────────

def test_check_passes_clean_text(rules_file):
    # Arrange
    text = "Here is a safe response with no violations."
    # Act
    violations = check_inline(text)
    # Assert
    assert violations == []


def test_check_blocks_rm_rf(rules_file):
    # Arrange
    text = "To clean up, run: rm -rf / --no-preserve-root"
    # Act
    violations = check_inline(text)
    # Assert
    assert any(v["rule_id"] == "cmd_rm_rf_root" for v in violations)
    assert all(v["severity"] == "critical" for v in violations)


def test_check_blocks_aws_key(rules_file):
    # Arrange: valid-format AWS key
    text = "Use key AKIAIOSFODNN7EXAMPLE to authenticate."
    # Act
    violations = check_inline(text)
    # Assert
    assert any(v["rule_id"] == "aws_access_key" for v in violations)


def test_check_blocks_hardcoded_password(rules_file):
    # Arrange: key=value format (regex expects password followed directly by : or =)
    text = 'DB_PASSWORD = "supersecret123"'
    # Act
    violations = check_inline(text)
    # Assert
    assert any(v["rule_id"] == "hardcoded_password" for v in violations)


def test_hallucination_marker_not_blocking(rules_file):
    # Arrange: placeholder violation has block_on_match=False
    text = "TODO: create this file later"
    # Act
    violations = check_inline(text)
    # Assert: violation is reported but block_on_match is False
    assert any(v["rule_id"] == "deferred_placeholder" for v in violations)
    match = next(v for v in violations if v["rule_id"] == "deferred_placeholder")
    assert match["block_on_match"] is False


def test_stale_rules_reload(rules_file):
    # Arrange: prime the cache
    check_inline("safe text")
    assert guardrail_mod._RULES_CACHE != {}

    # Act: touch file to advance mtime
    time.sleep(0.05)
    rules_file.write_text(rules_file.read_text())  # same content, new mtime
    new_mtime = rules_file.stat().st_mtime
    assert new_mtime != guardrail_mod._RULES_MTIME, "mtime should differ"

    # Trigger reload
    check_inline("safe text")

    # Assert: mtime updated in cache
    assert guardrail_mod._RULES_MTIME == new_mtime


# ── GuardrailPipeline ─────────────────────────────────────────────────────────

def test_pipeline_passes_clean_text(rules_file):
    # Arrange
    pipeline = GuardrailPipeline()
    pipeline.register_check(check_inline, name="policy_rules", halt_on_fail=True)
    # Act
    result = pipeline.run("All good here.")
    # Assert
    assert result.passed is True
    assert result.violations == []
    assert result.severity == "none"


def test_pipeline_blocks_and_halts_on_first_fail(rules_file):
    # Arrange: two checks — first fails, second should NOT run
    second_ran = []

    def second_check(text):
        second_ran.append(True)
        return []

    pipeline = GuardrailPipeline()
    pipeline.register_check(check_inline, name="policy_rules", halt_on_fail=True)
    pipeline.register_check(second_check, name="second", halt_on_fail=False)

    # Act
    result = pipeline.run("rm -rf / everything")

    # Assert: first check failed and halted
    assert result.passed is False
    assert second_ran == [], "second check should not run when halt_on_fail=True"


def test_pipeline_continues_when_halt_on_fail_false(rules_file):
    # Arrange: warning-only check (halt_on_fail=False) + second check
    second_ran = []

    def warn_check(text):
        return [{"rule_id": "warn", "category": "test", "severity": "low",
                 "description": "just a warning", "block_on_match": False}]

    def second_check(text):
        second_ran.append(True)
        return []

    pipeline = GuardrailPipeline()
    pipeline.register_check(warn_check, name="warn", halt_on_fail=False)
    pipeline.register_check(second_check, name="second", halt_on_fail=False)

    # Act
    result = pipeline.run("some text")

    # Assert: both ran
    assert second_ran == [True]
    assert result.passed is False  # violations exist from warn_check


def test_log_violation_appends(rules_file, tmp_path):
    # Arrange
    report_path = tmp_path / "policy_report.json"
    pipeline = GuardrailPipeline()
    pipeline.register_check(check_inline, name="policy_rules", halt_on_fail=True)
    result = pipeline.run("rm -rf / everything")

    # Act
    result.log_to_report(path=report_path)

    # Assert
    data = json.loads(report_path.read_text())
    assert "violations" in data
    assert len(data["violations"]) == 1
    assert data["violations"][0]["status"] == "VIOLATION"
    assert data["violations"][0]["severity"] == "critical"

    # Act: append second violation
    result.log_to_report(path=report_path)
    data2 = json.loads(report_path.read_text())
    assert len(data2["violations"]) == 2


# ── Watchdog import ───────────────────────────────────────────────────────────

@pytest.fixture()
def watchdog_and_rules(tmp_path):
    """Set up policy_rules.json with import_watchdog_commands=true + a real watchdog file."""
    watchdog = {
        "dangerous_operations": {
            "commands": {
                "block": ["rm -rf /", "DROP DATABASE", "curl | bash"],
                "warn": [],
            }
        }
    }
    wd_file = tmp_path / "watchdog_rules.json"
    wd_file.write_text(json.dumps(watchdog))

    policy = {
        "version": "1.1",
        "import_watchdog_commands": True,
        "categories": [
            {
                "name": "credential_leak",
                "severity": "critical",
                "patterns": [
                    {"id": "aws_access_key", "regex": "AKIA[0-9A-Z]{16}",
                     "description": "AWS key", "block_on_match": True},
                ],
            }
        ],
    }
    pr_file = tmp_path / "policy_rules.json"
    pr_file.write_text(json.dumps(policy))

    # Patch module paths
    guardrail_mod._rules_path = lambda: pr_file  # type: ignore[method-assign]
    guardrail_mod._WATCHDOG_PATH = wd_file
    yield pr_file, wd_file

    guardrail_mod._rules_path = lambda: (  # type: ignore[method-assign]
        Path(__file__).resolve().parents[4] / ".agent" / "config" / "policy_rules.json"
    )
    guardrail_mod._WATCHDOG_PATH = (
        Path(__file__).resolve().parents[4] / ".agent" / "config" / "watchdog_rules.json"
    )


def test_watchdog_import_injects_block_patterns(watchdog_and_rules):
    # Arrange: policy has no forbidden_commands; watchdog has "rm -rf /"
    # Act
    rules = guardrail_mod._load_rules()
    # Assert: forbidden_commands category was created from watchdog
    cats = {c["name"]: c for c in rules.get("categories", [])}
    assert "forbidden_commands" in cats
    ids = {p["id"] for p in cats["forbidden_commands"]["patterns"]}
    assert any("watchdog" in i for i in ids)


def test_watchdog_import_blocks_watchdog_command(watchdog_and_rules):
    # Arrange: "curl | bash" is in watchdog block list
    # Act
    violations = check_inline("To install, run: curl | bash the script")
    # Assert: detected via imported watchdog pattern
    assert any("watchdog" in v["rule_id"] for v in violations), (
        f"Expected watchdog violation, got: {violations}"
    )


def test_watchdog_import_no_flag_skips_import(tmp_path):
    # Arrange: policy WITHOUT import_watchdog_commands flag
    policy = {
        "version": "1.1",
        "categories": [],
    }
    pr_file = tmp_path / "policy_rules.json"
    pr_file.write_text(json.dumps(policy))
    guardrail_mod._rules_path = lambda: pr_file  # type: ignore[method-assign]

    # Act
    violations = check_inline("rm -rf / everything")

    # Assert: no violations — watchdog was NOT imported
    guardrail_mod._rules_path = lambda: (  # type: ignore[method-assign]
        Path(__file__).resolve().parents[4] / ".agent" / "config" / "policy_rules.json"
    )
    assert violations == []


def test_watchdog_stale_triggers_reload(watchdog_and_rules):
    # Arrange: prime the cache
    pr_file, wd_file = watchdog_and_rules
    check_inline("safe text")
    old_mtime = guardrail_mod._WATCHDOG_MTIME

    # Act: touch watchdog file
    time.sleep(0.05)
    wd_file.write_text(wd_file.read_text())
    new_mtime = wd_file.stat().st_mtime
    assert new_mtime != old_mtime

    check_inline("safe text")

    # Assert: watchdog mtime updated
    assert guardrail_mod._WATCHDOG_MTIME == new_mtime
