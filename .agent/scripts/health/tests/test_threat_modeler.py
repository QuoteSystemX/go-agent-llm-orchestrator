#!/usr/bin/env python3
"""Unit tests for threat_modeler.py (Plan B). AAA pattern."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPTS_DIR))

from health import threat_modeler as tm


# ── parse_diff_to_files ───────────────────────────────────────────────────────

def test_parse_diff_to_files_returns_modified_paths():
    # Arrange
    diff = (
        "diff --git a/src/api.py b/src/api.py\n"
        "--- a/src/api.py\n"
        "+++ b/src/api.py\n"
        "@@ -1,3 +1,4 @@\n"
        "+import os\n"
        " def foo(): pass\n"
    )
    # Act
    files = tm.parse_diff_to_files(diff)
    # Assert
    assert files == ["src/api.py"]


def test_parse_diff_to_files_multiple():
    # Arrange
    diff = "+++ b/auth/login.py\n+++ b/models/user.py\n"
    # Act
    files = tm.parse_diff_to_files(diff)
    # Assert
    assert files == ["auth/login.py", "models/user.py"]


def test_parse_diff_to_files_empty_diff():
    # Arrange / Act / Assert
    assert tm.parse_diff_to_files("") == []


# ── _validate_threat ─────────────────────────────────────────────────────────

def _make_threat(**overrides) -> dict:
    base = {
        "threat_type": "SQL Injection",
        "stride_category": "Tampering",
        "severity": "High",
        "component": "db/query.py",
        "description": "Unsanitized input passed to query.",
        "mitigation": "Use parameterized queries.",
    }
    base.update(overrides)
    return base


def test_validate_threat_valid():
    assert tm._validate_threat(_make_threat()) is True


def test_validate_threat_missing_key():
    # Arrange: remove required key
    t = _make_threat()
    del t["mitigation"]
    # Act / Assert
    assert tm._validate_threat(t) is False


def test_validate_threat_invalid_severity():
    assert tm._validate_threat(_make_threat(severity="Critical")) is False


def test_validate_threat_invalid_stride_category():
    assert tm._validate_threat(_make_threat(stride_category="Phishing")) is False


def test_validate_threat_all_valid_severities():
    for sev in ("High", "Medium", "Low"):
        assert tm._validate_threat(_make_threat(severity=sev)) is True


def test_validate_threat_all_valid_stride():
    for cat in tm.VALID_STRIDE:
        assert tm._validate_threat(_make_threat(stride_category=cat)) is True


# ── generate_threat_model ─────────────────────────────────────────────────────

def test_generate_threat_model_returns_validated_list():
    # Arrange: LLM returns 2 valid threats + 1 invalid
    valid1 = _make_threat()
    valid2 = _make_threat(threat_type="Path Traversal", stride_category="Information Disclosure", severity="Medium")
    invalid = {"threat_type": "Bad", "severity": "Unknown"}  # missing keys
    llm_response = json.dumps([valid1, valid2, invalid])

    with patch.object(tm, "query_llm_safe", return_value=(llm_response, "ollama", {})):
        # Act
        threats = tm.generate_threat_model("diff content", ["src/api.py"])

    # Assert
    assert len(threats) == 2
    assert all(tm._validate_threat(t) for t in threats)


def test_generate_threat_model_stub_returns_empty():
    # Arrange: source == "stub" → graceful fallback
    with patch.object(tm, "query_llm_safe", return_value=("{}", "stub", {})):
        threats = tm.generate_threat_model("diff", [])
    assert threats == []


def test_generate_threat_model_malformed_json_returns_empty():
    # Arrange
    with patch.object(tm, "query_llm_safe", return_value=("not-json!!!", "ollama", {})):
        threats = tm.generate_threat_model("diff", [])
    assert threats == []


def test_generate_threat_model_wrapped_dict():
    # Arrange: some models return {"threats": [...]}
    wrapped = json.dumps({"threats": [_make_threat()]})
    with patch.object(tm, "query_llm_safe", return_value=(wrapped, "ollama", {})):
        threats = tm.generate_threat_model("diff", [])
    assert len(threats) == 1


# ── save_threat_model ─────────────────────────────────────────────────────────

def test_save_threat_model_writes_json(tmp_path):
    # Arrange
    with patch.object(tm, "FORESIGHT_DIR", tmp_path), \
         patch.object(tm, "THREAT_REPORT", tmp_path / "threat_model.json"), \
         patch.object(tm, "_get_current_commit", return_value="abc1234"):
        # Act
        tm.save_threat_model([_make_threat()])

    # Assert
    report = json.loads((tmp_path / "threat_model.json").read_text())
    assert report["metadata"]["commit"] == "abc1234"
    assert len(report["threats"]) == 1
    assert report["metadata"]["threat_count"] == 1


def test_save_threat_model_empty_threats(tmp_path):
    with patch.object(tm, "FORESIGHT_DIR", tmp_path), \
         patch.object(tm, "THREAT_REPORT", tmp_path / "threat_model.json"), \
         patch.object(tm, "_get_current_commit", return_value="000"):
        tm.save_threat_model([])

    report = json.loads((tmp_path / "threat_model.json").read_text())
    assert report["threats"] == []
    assert report["metadata"]["threat_count"] == 0


# ── _print_audit_warning ──────────────────────────────────────────────────────

def test_print_audit_warning_shown_for_high_no_mitigation(capsys):
    # Arrange: High threat with empty mitigation
    t = _make_threat(severity="High", mitigation="")
    # Act
    tm._print_audit_warning([t])
    # Assert
    out = capsys.readouterr().out
    assert "SECURITY AUDIT WARNING" in out
    assert t["threat_type"] in out


def test_print_audit_warning_not_shown_when_mitigated(capsys):
    # Arrange: High threat WITH mitigation
    t = _make_threat(severity="High", mitigation="Use parameterized queries.")
    tm._print_audit_warning([t])
    out = capsys.readouterr().out
    assert "SECURITY AUDIT WARNING" not in out


def test_print_audit_warning_not_shown_for_medium(capsys):
    t = _make_threat(severity="Medium", mitigation="")
    tm._print_audit_warning([t])
    out = capsys.readouterr().out
    assert "SECURITY AUDIT WARNING" not in out


# ── analyze (integration stub) ────────────────────────────────────────────────

def test_analyze_skips_on_empty_diff(tmp_path, capsys):
    # Arrange
    with patch.object(tm, "get_staged_diff", return_value=""), \
         patch.object(tm, "FORESIGHT_DIR", tmp_path), \
         patch.object(tm, "THREAT_REPORT", tmp_path / "threat_model.json"), \
         patch.object(tm, "_get_current_commit", return_value="abc"):
        result = tm.analyze()

    out = capsys.readouterr().out
    assert result == []
    assert "No staged changes" in out


def test_analyze_returns_validated_threats(tmp_path):
    # Arrange
    fake_diff = "+++ b/auth.py\n+password = input()\n"
    threat = _make_threat()
    with patch.object(tm, "get_staged_diff", return_value=fake_diff), \
         patch.object(tm, "generate_threat_model", return_value=[threat]), \
         patch.object(tm, "FORESIGHT_DIR", tmp_path), \
         patch.object(tm, "THREAT_REPORT", tmp_path / "threat_model.json"), \
         patch.object(tm, "_get_current_commit", return_value="abc"):
        result = tm.analyze(diff=fake_diff)

    assert len(result) == 1
    assert result[0]["threat_type"] == "SQL Injection"
