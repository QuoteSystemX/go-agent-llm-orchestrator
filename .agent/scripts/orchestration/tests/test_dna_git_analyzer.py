#!/usr/bin/env python3
"""Unit tests for dna_git_analyzer — pure logic, no git/filesystem I/O. AAA pattern."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR.parent))

from orchestration.dna_git_analyzer import (
    check_discrepancy,
    compute_confidence,
    compute_dna,
    compute_metrics,
    parse_git_log,
    score_axes,
)


# ── parse_git_log ─────────────────────────────────────────────────────────────

def test_parse_git_log_empty_output():
    # Arrange + Act + Assert
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = ""
        result = parse_git_log("nobody")
    assert result == []


def test_parse_git_log_parses_files():
    # Arrange
    fake_output = (
        "COMMIT:abc123|feat: add feature\n"
        "src/main.py\n"
        "tests/test_main.py\n"
        "\n"
        "COMMIT:def456|fix: patch bug\n"
        "src/util.py\n"
    )
    # Act
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = fake_output
        commits = parse_git_log("author")
    # Assert
    assert len(commits) == 2
    assert commits[0]["message"] == "feat: add feature"
    assert "tests/test_main.py" in commits[0]["files"]
    assert commits[1]["files"] == ["src/util.py"]


def test_parse_git_log_nonzero_returns_empty():
    # Arrange + Act
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 128
        mock_run.return_value.stdout = ""
        result = parse_git_log("author")
    # Assert
    assert result == []


# ── compute_metrics ───────────────────────────────────────────────────────────

def test_metrics_empty_commits():
    # Arrange + Act
    result = compute_metrics([])
    # Assert
    assert result == {"total_commits": 0}


def test_metrics_test_ratio():
    # Arrange: 2 commits, 1 test file
    commits = [
        {"hash": "a", "message": "feat: thing", "files": ["src/main.py", "tests/test_main.py"]},
        {"hash": "b", "message": "fix: bug", "files": ["src/util.py"]},
    ]
    # Act
    m = compute_metrics(commits)
    # Assert
    assert m["total_commits"] == 2
    assert m["test_ratio"] == pytest.approx(1 / 3, rel=0.01)
    assert m["avg_files_per_commit"] == pytest.approx(1.5, rel=0.01)


def test_metrics_commit_type_extraction():
    # Arrange
    commits = [
        {"hash": "a", "message": "feat: new thing", "files": []},
        {"hash": "b", "message": "fix: patch", "files": []},
        {"hash": "c", "message": "fix: another patch", "files": []},
        {"hash": "d", "message": "refactor: cleanup", "files": []},
    ]
    # Act
    m = compute_metrics(commits)
    # Assert
    assert m["commit_types"]["feat"] == 1
    assert m["commit_types"]["fix"] == 2
    assert m["commit_types"]["refactor"] == 1


def test_metrics_keywords():
    # Arrange
    commits = [
        {"hash": "a", "message": "fix: simplify auth logic", "files": []},
        {"hash": "b", "message": "hack: wip experiment", "files": []},
        {"hash": "c", "message": "feat: extract helper", "files": []},
    ]
    # Act
    m = compute_metrics(commits)
    # Assert
    assert m["msg_keywords"].get("simplify", 0) == 1
    assert m["msg_keywords"].get("hack", 0) == 1
    assert m["msg_keywords"].get("extract", 0) == 1


# ── score_axes ────────────────────────────────────────────────────────────────

def test_score_axes_fix_heavy_minimal():
    # Arrange: many fixes, small commits
    metrics = {
        "total_commits": 20,
        "avg_files_per_commit": 1.5,
        "test_ratio": 0.05,
        "comment_density": 0.02,
        "commit_types": {"fix": 14, "feat": 3, "chore": 3},
        "msg_keywords": {},
    }
    # Act
    scores = score_axes(metrics)
    # Assert: pragmatic and minimal should dominate
    assert scores["pragmatic"] > scores["clean"]
    assert scores["pragmatic"] > scores["creative"]
    assert scores["minimal"] >= scores["tdd"]


def test_score_axes_feat_heavy_creative():
    # Arrange: many features, broad commits
    metrics = {
        "total_commits": 30,
        "avg_files_per_commit": 7,
        "test_ratio": 0.10,
        "comment_density": 0.01,
        "commit_types": {"feat": 24, "fix": 4, "chore": 2},
        "msg_keywords": {},
    }
    # Act
    scores = score_axes(metrics)
    # Assert
    assert scores["creative"] > scores["clean"]
    assert scores["creative"] > scores["pragmatic"]


def test_score_axes_refactor_tdd():
    # Arrange: heavy refactor + high test ratio
    metrics = {
        "total_commits": 40,
        "avg_files_per_commit": 4,
        "test_ratio": 0.40,
        "comment_density": 0.05,
        "commit_types": {"refactor": 16, "feat": 10, "fix": 8, "test": 6},
        "msg_keywords": {"refactor": 8},
    }
    # Act
    scores = score_axes(metrics)
    # Assert
    assert scores["clean"] > scores["pragmatic"]
    assert scores["tdd"] > scores["minimal"]


def test_score_axes_empty_metrics_fallback():
    # Arrange
    metrics = {"total_commits": 5, "avg_files_per_commit": 2, "test_ratio": 0,
               "comment_density": 0, "commit_types": {}, "msg_keywords": {}}
    # Act
    scores = score_axes(metrics)
    # Assert: fallback should give pragmatic some score
    assert scores["pragmatic"] > 0


# ── compute_dna ───────────────────────────────────────────────────────────────

def test_compute_dna_returns_correct_labels():
    # Arrange
    scores = {"clean": 0.1, "pragmatic": 5.0, "creative": 0.5,
              "tdd": 0.2, "codefirst": 0.5, "minimal": 3.0}
    # Act
    primary, secondary = compute_dna(scores)
    # Assert
    assert primary == "PRAGMATIC"
    assert secondary == "MINIMALIST"


# ── compute_confidence ────────────────────────────────────────────────────────

def test_confidence_range():
    # Arrange
    scores = {"clean": 1.5, "pragmatic": 3.0, "creative": 0.5,
              "tdd": 0.2, "codefirst": 0.8, "minimal": 2.5}
    metrics = {"total_commits": 60}
    # Act
    conf = compute_confidence(scores, metrics)
    # Assert
    assert 0.10 <= conf <= 0.99


def test_confidence_low_for_sparse_data():
    # Arrange: all zeros, 3 commits
    scores = {k: 0.0 for k in ["clean", "pragmatic", "creative", "tdd", "codefirst", "minimal"]}
    metrics = {"total_commits": 3}
    # Act
    conf = compute_confidence(scores, metrics)
    # Assert
    assert conf < 0.5


# ── check_discrepancy ─────────────────────────────────────────────────────────

def test_discrepancy_detected(tmp_path):
    # Arrange: wizard set a different DNA
    bus = tmp_path / "user_dna.json"
    bus.write_text(json.dumps({"dna": "ARCHITECT / TDD"}))
    # Act
    result = check_discrepancy("PRAGMATIC / MINIMALIST", bus_file=bus)
    # Assert
    assert result == "ARCHITECT / TDD"


def test_no_discrepancy_when_matching(tmp_path):
    # Arrange
    bus = tmp_path / "user_dna.json"
    bus.write_text(json.dumps({"dna": "PRAGMATIC / MINIMALIST"}))
    # Act
    result = check_discrepancy("PRAGMATIC / MINIMALIST", bus_file=bus)
    # Assert
    assert result is None


def test_no_discrepancy_when_bus_missing(tmp_path):
    # Arrange: no file
    # Act
    result = check_discrepancy("PRAGMATIC / MINIMALIST", bus_file=tmp_path / "missing.json")
    # Assert
    assert result is None
