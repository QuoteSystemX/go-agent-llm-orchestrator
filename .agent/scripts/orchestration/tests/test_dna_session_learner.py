#!/usr/bin/env python3
"""Unit tests for dna_session_learner — pure logic, no filesystem I/O. AAA pattern."""

import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR.parent))

from orchestration.dna_session_learner import (
    compute_dna,
    compute_stability,
    confidence_change,
    diff_events,
    drift_immediate,
    drift_rolling,
    fuse_scores,
    score_from_outputs,
    score_from_telemetry,
    stability_cross_source,
    stability_historical,
)

_ZERO = {k: 0.0 for k in ["clean", "pragmatic", "creative", "tdd", "codefirst", "minimal"]}


# ── score_from_telemetry ──────────────────────────────────────────────────────

def test_l1_events_boost_pragmatic():
    # Arrange
    events = [{"tier": "L1", "task": "simple"}, {"tier": "L1", "task": "simple"}]
    # Act
    scores = score_from_telemetry(events)
    # Assert
    assert scores["pragmatic"] > scores["clean"]
    assert scores["minimal"] > scores["tdd"]


def test_l4_events_boost_clean_and_creative():
    # Arrange
    events = [{"tier": "L4", "task": "architecture"}, {"tier": "L4", "task": "refactor"}]
    # Act
    scores = score_from_telemetry(events)
    # Assert
    assert scores["clean"] > scores["pragmatic"]


def test_empty_events_returns_zeros():
    # Arrange + Act
    scores = score_from_telemetry([])
    # Assert
    assert all(v == 0.0 for v in scores.values())


# ── score_from_outputs ────────────────────────────────────────────────────────

def test_fix_goals_boost_pragmatic():
    # Arrange
    goals = ["fix login bug", "fix timeout", "patch stale cache"]
    # Act
    scores = score_from_outputs(goals)
    # Assert
    assert scores["pragmatic"] > 0
    assert scores["minimal"] > 0


def test_refactor_goals_boost_clean():
    # Arrange
    goals = ["refactor auth module", "extract helper", "cleanup old code"]
    # Act
    scores = score_from_outputs(goals)
    # Assert
    assert scores["clean"] > scores["creative"]


def test_tdd_keyword_boosts_tdd_axis():
    # Arrange
    goals = ["add tdd tests for payment", "write test spec for order"]
    # Act
    scores = score_from_outputs(goals)
    # Assert
    assert scores["tdd"] > 0


# ── fuse_scores ───────────────────────────────────────────────────────────────

def test_fuse_weights_sum_correctly():
    # Arrange: only telemetry has signal
    telem = {k: 10.0 if k == "pragmatic" else 0.0 for k in _ZERO}
    outputs = _ZERO.copy()
    git = _ZERO.copy()
    # Act
    fused = fuse_scores(telem, outputs, git)
    # Assert: pragmatic gets 10 * 0.4 = 4.0
    assert fused["pragmatic"] == pytest.approx(4.0, rel=0.01)


def test_fuse_all_sources_contribute():
    # Arrange
    telem = {**_ZERO, "clean": 5.0}
    outputs = {**_ZERO, "pragmatic": 5.0}
    git = {**_ZERO, "creative": 5.0}
    # Act
    fused = fuse_scores(telem, outputs, git)
    # Assert: all three get some weight
    assert fused["clean"] > 0
    assert fused["pragmatic"] > 0
    assert fused["creative"] > 0


# ── compute_dna ───────────────────────────────────────────────────────────────

def test_compute_dna_pragmatic_minimalist():
    # Arrange
    scores = {**_ZERO, "pragmatic": 5.0, "minimal": 3.0}
    # Act
    assert compute_dna(scores) == "PRAGMATIC / MINIMALIST"


def test_compute_dna_architect_tdd():
    # Arrange
    scores = {**_ZERO, "clean": 6.0, "tdd": 4.0}
    # Act
    assert compute_dna(scores) == "ARCHITECT / TDD"


# ── stability ─────────────────────────────────────────────────────────────────

def test_stability_cross_source_full_agreement():
    # Arrange: all three sources agree on pragmatic
    s = {**_ZERO, "pragmatic": 5.0}
    # Act
    result = stability_cross_source(s, s, s)
    # Assert
    assert result == 1.0


def test_stability_cross_source_full_disagreement():
    # Arrange: each source points to different primary
    t = {**_ZERO, "clean": 5.0}
    o = {**_ZERO, "pragmatic": 5.0}
    g = {**_ZERO, "creative": 5.0}
    # Act
    result = stability_cross_source(t, o, g)
    # Assert
    assert result == 0.0


def test_stability_historical_returns_none_below_3():
    # Arrange
    history = [{"axis_scores": {**_ZERO, "pragmatic": 3.0}}]
    # Act
    assert stability_historical(history) is None


def test_stability_historical_stable_history():
    # Arrange: consistent high pragmatic score
    event = {"axis_scores": {**_ZERO, "pragmatic": 4.0}}
    history = [event] * 5
    # Act
    result = stability_historical(history)
    # Assert: all same → stddev=0 → stability=1.0
    assert result == pytest.approx(1.0, abs=0.01)


def test_compute_stability_uses_cross_source_when_no_history():
    # Arrange
    s_agree = {**_ZERO, "pragmatic": 5.0}
    result = compute_stability(s_agree, s_agree, s_agree, history=[])
    # Assert: cross-source agrees → 1.0
    assert result == 1.0


# ── drift ─────────────────────────────────────────────────────────────────────

def test_drift_immediate_detects_large_shift():
    # Arrange
    scores = {**_ZERO, "clean": 5.0}
    prev = {"axis_scores": {**_ZERO, "pragmatic": 5.0}}
    # Act
    assert drift_immediate(scores, prev) is True


def test_drift_immediate_no_shift():
    # Arrange
    scores = {**_ZERO, "pragmatic": 5.0}
    prev = {"axis_scores": {**_ZERO, "pragmatic": 5.1}}
    # Act
    assert drift_immediate(scores, prev) is False


def test_drift_immediate_false_when_no_prev():
    # Arrange + Act
    assert drift_immediate({}, None) is False


def test_drift_rolling_detects_shift():
    # Arrange: last 3 events have much higher clean than prior 3
    low = {"axis_scores": {**_ZERO, "pragmatic": 1.0}}
    high = {"axis_scores": {**_ZERO, "clean": 5.0}}
    history = [low] * 3 + [high] * 3
    # Act
    assert drift_rolling(history) is True


def test_drift_rolling_stable():
    # Arrange: all events identical
    ev = {"axis_scores": {**_ZERO, "pragmatic": 4.0}}
    history = [ev] * 6
    # Act
    assert drift_rolling(history) is False


def test_drift_rolling_false_below_6_events():
    # Arrange
    ev = {"axis_scores": {**_ZERO, "pragmatic": 4.0}}
    history = [ev] * 4
    # Act
    assert drift_rolling(history) is False


# ── confidence_change ─────────────────────────────────────────────────────────

def test_confidence_change_positive():
    # Arrange: session scores higher than git baseline
    scores = {**_ZERO, "clean": 6.0}
    git = {**_ZERO, "clean": 2.0}
    # Act
    result = confidence_change(scores, git)
    # Assert
    assert result > 0


def test_confidence_change_zero_no_git():
    # Arrange + Act
    result = confidence_change({**_ZERO, "pragmatic": 3.0}, {})
    # Assert
    assert isinstance(result, float)


# ── diff_events ───────────────────────────────────────────────────────────────

def test_diff_events_needs_two(capsys):
    # Arrange: only one event
    history = [{"timestamp": "2026-01-01T00:00:00+00:00", "axis_scores": _ZERO,
                "dna_tag": "A", "dna_stability": 1.0, "drift_detected": False}]
    # Act
    diff_events(history)
    # Assert
    out = capsys.readouterr().out
    assert "Need at least 2" in out
