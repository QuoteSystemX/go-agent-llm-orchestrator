#!/usr/bin/env python3
"""Unit tests for dna_orchestrator — pure logic, no I/O. AAA pattern."""

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR.parent))

from orchestration.dna_orchestrator import (
    merge_dna,
    _append_evolution_event,
    _should_skip_interval,
    EVOLUTION_LOG,
)


# ── merge_dna ─────────────────────────────────────────────────────────────────

_ZERO = {k: 0.0 for k in ["clean", "pragmatic", "creative", "tdd", "codefirst", "minimal"]}


def test_merge_dna_weighted_by_confidence():
    # Arrange: high-confidence git says PRAGMATIC, low-confidence session says ARCHITECT
    results = [
        {"tag": "PRAGMATIC / MINIMALIST", "confidence": 0.8,
         "axis_scores": {**_ZERO, "pragmatic": 5.0, "minimal": 3.0}, "skipped": False},
        {"tag": "ARCHITECT / TDD", "confidence": 0.2,
         "axis_scores": {**_ZERO, "clean": 5.0, "tdd": 3.0}, "skipped": False},
    ]
    # Act
    tag, conf, scores = merge_dna(results)
    # Assert: pragmatic should dominate (0.8 weight)
    assert "PRAGMATIC" in tag
    assert scores["pragmatic"] > scores["clean"]


def test_merge_dna_skips_skipped_phases():
    # Arrange: one real result, one skipped
    results = [
        {"tag": "ARCHITECT / TDD", "confidence": 0.75,
         "axis_scores": {**_ZERO, "clean": 4.0, "tdd": 3.0}, "skipped": False},
        {"tag": "BALANCED", "confidence": 0.0, "axis_scores": {}, "skipped": True},
    ]
    # Act
    tag, conf, scores = merge_dna(results)
    # Assert: uses only the non-skipped result
    assert "ARCHITECT" in tag


def test_merge_dna_fallback_when_no_axis_scores():
    # Arrange: all skipped (onboarding only, no axis_scores)
    results = [
        {"tag": "PRAGMATIC / MINIMALIST", "confidence": 0.6, "axis_scores": {}, "skipped": False},
        {"tag": "BALANCED", "confidence": 0.1, "axis_scores": {}, "skipped": True},
    ]
    # Act: falls back to highest confidence winner
    tag, conf, _ = merge_dna(results)
    # Assert
    assert tag == "PRAGMATIC / MINIMALIST"


def test_merge_dna_equal_confidence():
    # Arrange: equal weights
    results = [
        {"tag": "PRAGMATIC / MINIMALIST", "confidence": 0.5,
         "axis_scores": {**_ZERO, "pragmatic": 6.0, "minimal": 2.0}, "skipped": False},
        {"tag": "PRAGMATIC / CODE-FIRST", "confidence": 0.5,
         "axis_scores": {**_ZERO, "pragmatic": 4.0, "codefirst": 3.0}, "skipped": False},
    ]
    # Act
    tag, conf, scores = merge_dna(results)
    # Assert: pragmatic dominant in both → PRAGMATIC primary
    assert "PRAGMATIC" in tag
    assert conf == pytest.approx(0.5, abs=0.01)


def test_merge_dna_all_skipped_returns_best_confidence():
    # Arrange
    results = [
        {"tag": "BALANCED", "confidence": 0.1, "axis_scores": {}, "skipped": True},
        {"tag": "PRAGMATIC / MINIMALIST", "confidence": 0.6, "axis_scores": {}, "skipped": True},
    ]
    # Act
    tag, conf, _ = merge_dna(results)
    # Assert: picks highest confidence even among skipped
    assert tag == "PRAGMATIC / MINIMALIST"


# ── _append_evolution_event ───────────────────────────────────────────────────

def test_append_evolution_creates_log(tmp_path):
    # Arrange
    log_path = tmp_path / "dna_evolution_log.json"
    # Act
    with patch("orchestration.dna_orchestrator.EVOLUTION_LOG", log_path):
        _append_evolution_event("git_analyzer", "[BALANCED]", "[PRAGMATIC / MINIMALIST]",
                                0.78, "78% fix commits", "semi", True)
    # Assert
    data = json.loads(log_path.read_text())
    assert len(data["events"]) == 1
    ev = data["events"][0]
    assert ev["phase"] == "git_analyzer"
    assert ev["new_dna"] == "[PRAGMATIC / MINIMALIST]"
    assert ev["user_approved"] is True


def test_append_evolution_accumulates(tmp_path):
    # Arrange: pre-existing log
    log_path = tmp_path / "dna_evolution_log.json"
    log_path.write_text(json.dumps({"events": [{"existing": True}]}))
    # Act
    with patch("orchestration.dna_orchestrator.EVOLUTION_LOG", log_path):
        _append_evolution_event("session_learner", "[A]", "[B]", 0.5, "reason", "auto", True)
    # Assert
    data = json.loads(log_path.read_text())
    assert len(data["events"]) == 2
    assert data["events"][0] == {"existing": True}


# ── _should_skip_interval ─────────────────────────────────────────────────────

def test_skip_interval_zero_never_skips():
    # Arrange + Act + Assert
    assert _should_skip_interval(0) is False


def test_skip_interval_no_log_never_skips(tmp_path):
    # Arrange: no evolution log
    missing = tmp_path / "no_log.json"
    with patch("orchestration.dna_orchestrator.EVOLUTION_LOG", missing):
        result = _should_skip_interval(5)
    assert result is False


def test_skip_interval_no_events_never_skips(tmp_path):
    # Arrange: empty events
    log_path = tmp_path / "log.json"
    log_path.write_text(json.dumps({"events": []}))
    with patch("orchestration.dna_orchestrator.EVOLUTION_LOG", log_path):
        result = _should_skip_interval(3)
    assert result is False
