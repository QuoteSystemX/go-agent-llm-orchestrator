#!/usr/bin/env python3
"""Unit tests for war_room_manager refactored Git-Ops helpers. AAA pattern."""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR.parent))

# Patch bus_manager before importing the module
_fake_bus = MagicMock()
_fake_bus.wait_for_object.return_value = None
_fake_bus.get_objects_by_type.return_value = []
with patch.dict("sys.modules", {"context": MagicMock(bus_manager=_fake_bus)}):
    from orchestration import war_room_manager as wrm


# ── _create_branch ────────────────────────────────────────────────────────────

def test_create_branch_success():
    # Arrange
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        # Act
        branch = wrm._create_branch("inc001")
    # Assert
    assert branch == "fix/inc-inc001"
    cmd = mock_run.call_args_list[0][0][0]
    assert "checkout" in cmd and "-b" in cmd and "fix/inc-inc001" in cmd


def test_create_branch_falls_back_when_exists():
    # Arrange: first call fails (branch exists), second succeeds
    results = [
        MagicMock(returncode=128, stderr="already exists"),
        MagicMock(returncode=0),
    ]
    with patch("subprocess.run", side_effect=results):
        # Act
        branch = wrm._create_branch("inc002")
    # Assert: fell back to checkout without -b
    assert branch == "fix/inc-inc002"


# ── _run_validation ───────────────────────────────────────────────────────────

def test_run_validation_passes():
    # Arrange
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="All checks pass", stderr="")
        # Act
        result = wrm._run_validation("fix/inc-test")
    # Assert
    assert result is True


def test_run_validation_fails():
    # Arrange
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="FAILED: drift detected", stderr="")
        # Act
        result = wrm._run_validation("fix/inc-test")
    # Assert
    assert result is False


# ── _commit_fix ───────────────────────────────────────────────────────────────

def test_commit_fix_skips_when_nothing_staged():
    # Arrange: git diff --name-only returns nothing, git diff --staged --quiet returns 0 (nothing staged)
    def side_effect(cmd, **kwargs):
        if "--name-only" in cmd:
            return MagicMock(returncode=0, stdout="")
        if "--staged" in cmd and "--quiet" in cmd:
            return MagicMock(returncode=0)  # 0 = nothing staged
        return MagicMock(returncode=0)

    with patch("subprocess.run", side_effect=side_effect):
        # Act
        result = wrm._commit_fix("fix/inc-test", "inc001")
    # Assert
    assert result is False


def test_commit_fix_commits_when_staged():
    # Arrange: nothing to add (diff empty), but staged changes exist (exit code 1)
    calls_log = []
    def side_effect(cmd, **kwargs):
        calls_log.append(cmd)
        if "--name-only" in cmd:
            return MagicMock(returncode=0, stdout="")
        if "--staged" in cmd and "--quiet" in cmd:
            return MagicMock(returncode=1)  # 1 = changes are staged
        return MagicMock(returncode=0)

    with patch("subprocess.run", side_effect=side_effect):
        # Act
        result = wrm._commit_fix("fix/inc-test", "inc001")
    # Assert
    assert result is True
    commit_cmd = next(c for c in calls_log if "commit" in c)
    assert "[AUTO-FIXED]" in " ".join(commit_cmd)
    assert "inc001" in " ".join(commit_cmd)


def test_commit_fix_stages_unstaged_changes():
    # Arrange: there are unstaged changes to add
    calls_log = []
    def side_effect(cmd, **kwargs):
        calls_log.append(cmd)
        if "--name-only" in cmd:
            return MagicMock(returncode=0, stdout="src/main.py\n")  # has changes
        if "--staged" in cmd and "--quiet" in cmd:
            return MagicMock(returncode=1)  # staged after add
        return MagicMock(returncode=0)

    with patch("subprocess.run", side_effect=side_effect):
        wrm._commit_fix("fix/inc-test", "inc001")
    # Assert: git add -A was called
    assert any("-A" in c for c in calls_log)


# ── _report_pr ────────────────────────────────────────────────────────────────

def test_report_pr_prints_branch_and_command(capsys):
    # Arrange + Act
    wrm._report_pr("fix/inc-myincident")
    # Assert
    out = capsys.readouterr().out
    assert "fix/inc-myincident" in out
    assert "gh pr create" in out


# ── _scan_repair_files ────────────────────────────────────────────────────────

def test_scan_repair_files_returns_unprocessed(tmp_path):
    # Arrange
    repair = tmp_path / "repair_20260529_120000.json"
    repair.write_text(json.dumps({"error": "NameError: x", "script_path": "foo.py"}))
    wrm._PROCESSED_REPAIRS.clear()

    with patch.object(wrm, "BUS_OUTPUTS", tmp_path):
        # Act
        incidents = wrm._scan_repair_files()

    # Assert
    assert len(incidents) == 1
    assert incidents[0]["id"].startswith("selfheal_")
    assert "NameError" in incidents[0]["content"]["stderr"]


def test_scan_repair_files_skips_processed(tmp_path):
    # Arrange
    repair = tmp_path / "repair_20260529_120001.json"
    repair.write_text(json.dumps({"error": "err"}))
    wrm._PROCESSED_REPAIRS.clear()
    wrm._PROCESSED_REPAIRS.add(str(repair))

    with patch.object(wrm, "BUS_OUTPUTS", tmp_path):
        # Act
        incidents = wrm._scan_repair_files()

    # Assert
    assert incidents == []


def test_scan_repair_files_empty_dir(tmp_path):
    # Arrange: no repair files
    with patch.object(wrm, "BUS_OUTPUTS", tmp_path):
        incidents = wrm._scan_repair_files()
    assert incidents == []


# ── _poll_bus ─────────────────────────────────────────────────────────────────

def test_poll_bus_returns_on_first_hit():
    # Arrange
    fake_obj = {"id": "found", "data": "value"}
    with patch.object(wrm, "bus_manager") as mock_bm:
        mock_bm.wait_for_object.return_value = fake_obj
        with patch("time.sleep"):
            # Act
            result = wrm._poll_bus("some_key", timeout=5)
    # Assert
    assert result == fake_obj


def test_poll_bus_returns_none_on_timeout():
    # Arrange: always returns None
    with patch.object(wrm, "bus_manager") as mock_bm:
        mock_bm.wait_for_object.return_value = None
        with patch("time.monotonic", side_effect=[0, 0.1, 31]):
            with patch("time.sleep"):
                # Act
                result = wrm._poll_bus("missing_key", timeout=30)
    # Assert
    assert result is None
