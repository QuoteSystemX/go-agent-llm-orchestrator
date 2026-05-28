#!/usr/bin/env python3
"""Unit tests for dna_onboarder — pure logic, no stdin/filesystem I/O. AAA pattern."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR.parent))

from orchestration.dna_onboarder import (
    _build_persona_content,
    _compute_dna,
    load_config,
    write_outputs,
    DEFAULT_CONFIG,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def config():
    return load_config(DEFAULT_CONFIG)


AXES = {
    "primary": ["clean", "pragmatic", "creative"],
    "secondary": ["tdd", "codefirst", "minimal"],
}
DNA_LABELS = {
    "clean": "ARCHITECT",
    "pragmatic": "PRAGMATIC",
    "creative": "VISIONARY",
    "tdd": "TDD",
    "codefirst": "CODE-FIRST",
    "minimal": "MINIMALIST",
}


# ── _compute_dna ──────────────────────────────────────────────────────────────

def test_compute_dna_pragmatic_minimalist():
    # Arrange
    scores = {"clean": 0, "pragmatic": 6, "creative": 1, "tdd": 0, "codefirst": 1, "minimal": 4}
    # Act
    primary, secondary = _compute_dna(scores, AXES, DNA_LABELS)
    # Assert
    assert primary == "PRAGMATIC"
    assert secondary == "MINIMALIST"


def test_compute_dna_architect_tdd():
    # Arrange
    scores = {"clean": 7, "pragmatic": 1, "creative": 2, "tdd": 5, "codefirst": 1, "minimal": 0}
    # Act
    primary, secondary = _compute_dna(scores, AXES, DNA_LABELS)
    # Assert
    assert primary == "ARCHITECT"
    assert secondary == "TDD"


def test_compute_dna_visionary_codefirst():
    # Arrange
    scores = {"clean": 1, "pragmatic": 2, "creative": 8, "tdd": 0, "codefirst": 4, "minimal": 1}
    # Act
    primary, secondary = _compute_dna(scores, AXES, DNA_LABELS)
    # Assert
    assert primary == "VISIONARY"
    assert secondary == "CODE-FIRST"


def test_compute_dna_all_zero_returns_first_axis_value():
    # Arrange: all zeros — deterministic tie-break → first in axis list
    scores = {"clean": 0, "pragmatic": 0, "creative": 0, "tdd": 0, "codefirst": 0, "minimal": 0}
    # Act
    primary, secondary = _compute_dna(scores, AXES, DNA_LABELS)
    # Assert: deterministic — max on equal scores picks first element
    assert primary in ("ARCHITECT", "PRAGMATIC", "VISIONARY")
    assert secondary in ("TDD", "CODE-FIRST", "MINIMALIST")


# ── _build_persona_content ────────────────────────────────────────────────────

def test_build_persona_exact_match(config):
    # Arrange
    dna_tag = "PRAGMATIC / MINIMALIST"
    # Act
    content = _build_persona_content(dna_tag, config["profiles"])
    # Assert
    assert f"## 🧬 Core DNA: [{dna_tag}]" in content
    assert "### 🛰️ Stylistic Preferences" in content
    assert "### 🛠️ Technical Philosophy" in content
    assert "KISS" in content


def test_build_persona_fallback_to_balanced(config):
    # Arrange: unknown combo
    dna_tag = "NONEXISTENT / COMBO"
    # Act
    content = _build_persona_content(dna_tag, config["profiles"])
    # Assert: uses BALANCED profile text but correct tag in header
    assert f"## 🧬 Core DNA: [{dna_tag}]" in content
    assert "Pragmatic Default" in content


def test_build_persona_all_known_combos(config):
    # Arrange + Act + Assert: every profile generates valid output
    for tag, profile in config["profiles"].items():
        if tag == "BALANCED":
            continue
        content = _build_persona_content(tag, config["profiles"])
        assert f"[{tag}]" in content
        assert len(profile["stylistic"]) >= 2
        assert len(profile["philosophy"]) >= 2


# ── load_config ───────────────────────────────────────────────────────────────

def test_config_has_five_questions(config):
    assert len(config["questions"]) == 5


def test_config_each_question_has_three_choices(config):
    for q in config["questions"]:
        assert len(q["choices"]) == 3, f"Question '{q['text']}' has wrong choice count"


def test_config_weights_cover_all_axes(config):
    axes_keys = set(config["axes"]["primary"]) | set(config["axes"]["secondary"])
    for q in config["questions"]:
        for choice in q["choices"]:
            assert set(choice["weights"].keys()) == axes_keys, (
                f"Choice '{choice['label']}' missing axis keys"
            )


# ── write_outputs dry-run ─────────────────────────────────────────────────────

def test_dry_run_prints_preview_no_writes(config, capsys, tmp_path):
    # Arrange
    dna_tag = "ARCHITECT / TDD"
    raw_answers = [{"question": "Q1", "answer": "A1"}]
    # Act
    with patch("orchestration.dna_onboarder.PERSONA_FILE", tmp_path / "PERSONA.md"):
        with patch("orchestration.dna_onboarder.DNA_BUS_FILE", tmp_path / "user_dna.json"):
            write_outputs(dna_tag, raw_answers, config, dry_run=True)
    # Assert: nothing written
    assert not (tmp_path / "PERSONA.md").exists()
    out = capsys.readouterr().out
    assert "DRY RUN" in out
    assert "ARCHITECT / TDD" in out
