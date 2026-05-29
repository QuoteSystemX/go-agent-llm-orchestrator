#!/usr/bin/env python3
"""
DNA Session Learner — hybrid drift detector.

Plan B (multi-signal fusion): fuses telemetry tiers, agent output keywords,
and git baseline into weighted axis scores on each run.
Plan C (event log): appends each run as an event; stability uses historical
stddev when ≥3 events are available, cross-source agreement otherwise.

Usage:
    python dna_session_learner.py           # analyze and append event
    python dna_session_learner.py --diff    # show delta vs previous event
    python dna_session_learner.py --replay  # recompute stability from full history
    python dna_session_learner.py --apply   # auto-write PERSONA.md on drift
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import stdev
from lib.suppress import suppress

REPO_ROOT = Path(__file__).resolve().parents[3]
BUS = REPO_ROOT / ".agent" / "bus"
CONFIG_PATH = REPO_ROOT / ".agent" / "config" / "dna_questions.json"
TELEMETRY_PATH = BUS / "telemetry.json"
GIT_ANALYSIS_PATH = BUS / "dna_git_analysis.json"
DNA_BUS_PATH = BUS / "user_dna.json"
METRICS_PATH = BUS / "dna_session_metrics.json"
PERSONA_FILE = REPO_ROOT / ".agent" / "rules" / "PERSONA.md"

PRIMARY_AXES = ["clean", "pragmatic", "creative"]
SECONDARY_AXES = ["tdd", "codefirst", "minimal"]
ALL_AXES = PRIMARY_AXES + SECONDARY_AXES
DNA_LABELS = {
    "clean": "ARCHITECT", "pragmatic": "PRAGMATIC", "creative": "VISIONARY",
    "tdd": "TDD", "codefirst": "CODE-FIRST", "minimal": "MINIMALIST",
}

# Tier → axis weights (L1=simple→pragmatic, L4=complex→clean/creative)
_TIER_WEIGHTS: dict[str, dict[str, float]] = {
    "L1": {"pragmatic": 2.0, "minimal": 2.0},
    "L2": {"pragmatic": 1.5, "codefirst": 1.0},
    "L3": {"clean": 1.5, "tdd": 1.0},
    "L4": {"clean": 2.0, "creative": 1.5, "tdd": 1.5},
}

# Goal/task keywords → axis scores
_KEYWORD_AXES: dict[str, list[str]] = {
    "feat": ["creative", "codefirst"], "build": ["creative", "codefirst"],
    "implement": ["codefirst", "creative"], "refactor": ["clean"],
    "extract": ["clean"], "cleanup": ["minimal", "pragmatic"],
    "fix": ["pragmatic", "minimal"], "patch": ["pragmatic"],
    "simplify": ["minimal", "pragmatic"], "test": ["tdd"], "spec": ["tdd"],
    "tdd": ["tdd"], "architecture": ["clean", "creative"],
    "abstract": ["clean"], "minimal": ["minimal"], "simple": ["pragmatic", "minimal"],
}


# ── Data loaders ──────────────────────────────────────────────────────────────

def _load_telemetry_events() -> list[dict]:
    try:
        data = json.loads(TELEMETRY_PATH.read_text())
        return data.get("events", [])
    except Exception:
        return []


def _load_output_goals() -> list[str]:
    goals = []
    outputs_dir = BUS / "outputs"
    if not outputs_dir.exists():
        return goals
    for f in outputs_dir.glob("*.json"):
        with suppress("dna_session_learner.goal_parse", level=logging.WARNING):
            data = json.loads(f.read_text())
            if g := data.get("goal", ""):
                goals.append(g)
    return goals


def _load_git_scores() -> dict[str, float]:
    try:
        data = json.loads(GIT_ANALYSIS_PATH.read_text())
        return data.get("axis_scores", {})
    except Exception:
        return {}


def _load_history() -> list[dict]:
    try:
        return json.loads(METRICS_PATH.read_text())
    except Exception:
        return []


# ── Signal scoring (Plan B) ───────────────────────────────────────────────────

def score_from_telemetry(events: list[dict]) -> dict[str, float]:
    scores: dict[str, float] = {k: 0.0 for k in ALL_AXES}
    for ev in events:
        tier = ev.get("tier", "")
        if tier in _TIER_WEIGHTS:
            for axis, w in _TIER_WEIGHTS[tier].items():
                scores[axis] += w
        # Task text keywords
        task = ev.get("task", "").lower()
        for kw, axes in _KEYWORD_AXES.items():
            if kw in task:
                for axis in axes:
                    scores[axis] += 0.3
    return scores


def score_from_outputs(goals: list[str]) -> dict[str, float]:
    scores: dict[str, float] = {k: 0.0 for k in ALL_AXES}
    for goal in goals:
        goal_l = goal.lower()
        for kw, axes in _KEYWORD_AXES.items():
            if kw in goal_l:
                for axis in axes:
                    scores[axis] += 1.0
    return scores


def fuse_scores(
    telem: dict[str, float],
    outputs: dict[str, float],
    git: dict[str, float],
) -> dict[str, float]:
    """Weighted fusion: 0.4 telemetry + 0.4 outputs + 0.2 git baseline."""
    fused: dict[str, float] = {}
    for axis in ALL_AXES:
        fused[axis] = round(
            telem.get(axis, 0.0) * 0.4
            + outputs.get(axis, 0.0) * 0.4
            + git.get(axis, 0.0) * 0.2,
            3,
        )
    return fused


def compute_dna(scores: dict[str, float]) -> str:
    primary = max(PRIMARY_AXES, key=lambda k: scores.get(k, 0.0))
    secondary = max(SECONDARY_AXES, key=lambda k: scores.get(k, 0.0))
    return f"{DNA_LABELS[primary]} / {DNA_LABELS[secondary]}"


# ── Stability (hybrid B+C) ────────────────────────────────────────────────────

def _top_primary(scores: dict[str, float]) -> str:
    return max(PRIMARY_AXES, key=lambda k: scores.get(k, 0.0))


def stability_cross_source(
    telem: dict[str, float],
    outputs: dict[str, float],
    git: dict[str, float],
) -> float:
    """Plan B: pairwise agreement on dominant primary axis across 3 sources."""
    tops = [_top_primary(s) for s in (telem, outputs, git) if any(s.values())]
    if len(tops) < 2:
        return 0.5
    pairs = [(tops[i], tops[j]) for i in range(len(tops)) for j in range(i + 1, len(tops))]
    return round(sum(a == b for a, b in pairs) / len(pairs), 3)


def stability_historical(history: list[dict]) -> float:
    """Plan C: 1 - stddev of dominant primary axis scores across last 10 events."""
    window = history[-10:]
    if len(window) < 3:
        return None  # type: ignore[return-value]
    top_scores = []
    for ev in window:
        s = ev.get("axis_scores", {})
        top_scores.append(max(s.get(k, 0.0) for k in PRIMARY_AXES))
    sd = stdev(top_scores) if len(top_scores) >= 2 else 0.0
    return round(max(0.0, min(1.0, 1.0 - sd * 2)), 3)


def compute_stability(
    telem: dict, outputs: dict, git: dict, history: list[dict]
) -> float:
    hist = stability_historical(history)
    cross = stability_cross_source(telem, outputs, git)
    if hist is None:
        return cross
    return round(0.5 * hist + 0.5 * cross, 3)


# ── Drift detection (hybrid B+C) ─────────────────────────────────────────────

def drift_immediate(scores: dict[str, float], prev: dict | None) -> bool:
    """Plan B: any axis shifted >0.3 vs previous event."""
    if not prev:
        return False
    prev_scores = prev.get("axis_scores", {})
    return any(abs(scores.get(k, 0) - prev_scores.get(k, 0)) > 0.3 for k in ALL_AXES)


def drift_rolling(history: list[dict]) -> bool:
    """Plan C: primary axis mean shifted between last-3 vs prior-3 window."""
    if len(history) < 6:
        return False
    recent = history[-3:]
    prior = history[-6:-3]

    def _mean_top(window):
        vals = [max(e.get("axis_scores", {}).get(k, 0) for k in PRIMARY_AXES) for e in window]
        return sum(vals) / len(vals)

    return abs(_mean_top(recent) - _mean_top(prior)) > 0.15


def confidence_change(scores: dict[str, float], git: dict[str, float]) -> float:
    """Delta between dominant primary score now vs git baseline."""
    cur = max(scores.get(k, 0.0) for k in PRIMARY_AXES)
    base = max(git.get(k, 0.0) for k in PRIMARY_AXES) if git else 0.0
    total = max(cur, base, 1.0)
    return round((cur - base) / total, 3)


# ── Event log (Plan C) ────────────────────────────────────────────────────────

def append_event(history: list[dict], event: dict) -> None:
    history.append(event)
    METRICS_PATH.write_text(json.dumps(history, indent=2), encoding="utf-8")


def diff_events(history: list[dict]) -> None:
    if len(history) < 2:
        print("ℹ️  Need at least 2 events for --diff.")
        return
    old, new = history[-2], history[-1]
    print(f"\n── Delta: {old['timestamp']} → {new['timestamp']} ──")
    old_s = old.get("axis_scores", {})
    new_s = new.get("axis_scores", {})
    for axis in ALL_AXES:
        delta = new_s.get(axis, 0.0) - old_s.get(axis, 0.0)
        if abs(delta) > 0.01:
            sign = "+" if delta > 0 else ""
            print(f"  {axis:12s}: {old_s.get(axis, 0):.2f} → {new_s.get(axis, 0):.2f}  ({sign}{delta:.2f})")
    print(f"  dna_tag    : {old.get('dna_tag')} → {new.get('dna_tag')}")
    print(f"  stability  : {old.get('dna_stability')} → {new.get('dna_stability')}")
    print(f"  drift      : {old.get('drift_detected')} → {new.get('drift_detected')}")


def replay(history: list[dict]) -> None:
    """Recompute stability for all events using full history context."""
    print(f"♻️  Replaying {len(history)} events…")
    for i, ev in enumerate(history):
        s = stability_historical(history[: i + 1])
        ev["dna_stability_replayed"] = s
        tag = compute_dna(ev.get("axis_scores", {}))
        print(f"  [{i+1:02d}] {ev['timestamp'][:10]}  dna={tag}  hist_stability={s}")
    METRICS_PATH.write_text(json.dumps(history, indent=2), encoding="utf-8")
    print("✅ Replayed metrics saved.")


# ── PERSONA.md update ─────────────────────────────────────────────────────────

def apply_to_persona(dna_tag: str) -> None:
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        profiles = config.get("profiles", {})
        profile = profiles.get(dna_tag, profiles.get("BALANCED", {}))
        stylistic = "\n".join(f"- {s}" for s in profile.get("stylistic", []))
        philosophy = "\n".join(f"- {p}" for p in profile.get("philosophy", []))
    except Exception:
        stylistic = "- Adapt to context."
        philosophy = "- Pragmatic default."

    content = f"""\
# User Personality Profile (DNA) 🎭

This document defines the preferred communication style, technical depth, and coding philosophy for the current workspace.

## 🧬 Core DNA: [{dna_tag}]

### 🛰️ Stylistic Preferences

{stylistic}

### 🛠️ Technical Philosophy

{philosophy}

---
> [!NOTE]
> This profile is automatically read by `personality_adapter.py` to tune agent behavior.
"""
    PERSONA_FILE.write_text(content, encoding="utf-8")
    print(f"✅ PERSONA.md updated → [{dna_tag}]")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="DNA Session Learner — hybrid drift detector")
    parser.add_argument("--diff", action="store_true", help="Show delta vs previous event")
    parser.add_argument("--replay", action="store_true", help="Recompute stability from full history")
    parser.add_argument("--apply", action="store_true", help="Auto-write PERSONA.md on drift")
    args = parser.parse_args()

    history = _load_history()

    if args.replay:
        replay(history)
        return

    if args.diff:
        diff_events(history)
        return

    print("🧬 DNA Session Learner — analyzing telemetry…")

    events = _load_telemetry_events()
    goals = _load_output_goals()
    git_scores = _load_git_scores()

    telem_scores = score_from_telemetry(events)
    output_scores = score_from_outputs(goals)
    fused = fuse_scores(telem_scores, output_scores, git_scores)

    dna_tag = compute_dna(fused)
    prev = history[-1] if history else None
    stability = compute_stability(telem_scores, output_scores, git_scores, history)
    drift = drift_immediate(fused, prev) or drift_rolling(history)
    conf_delta = confidence_change(fused, git_scores)

    print(f"  telemetry events : {len(events)}")
    print(f"  output goals     : {len(goals)}")
    print(f"  git axis scores  : {'available' if git_scores else 'not found'}")
    print(f"\n🧬 Detected DNA  : [{dna_tag}]")
    print(f"  dna_stability   : {stability:.2f}")
    print(f"  drift_detected  : {drift}")
    print(f"  confidence_Δ    : {conf_delta:+.3f}")

    event: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "axis_scores": fused,
        "dna_tag": dna_tag,
        "dna_stability": stability,
        "drift_detected": drift,
        "confidence_change": conf_delta,
        "sources": {
            "telemetry_events": len(events),
            "output_files": len(goals),
            "git_commits": json.loads(GIT_ANALYSIS_PATH.read_text()).get("commits_analyzed", 0)
            if GIT_ANALYSIS_PATH.exists() else 0,
        },
    }
    append_event(history, event)
    print(f"\n💾 Event #{len(history)} appended → {METRICS_PATH.relative_to(REPO_ROOT)}")

    if drift and stability < 0.3:
        print(f"\n⚠️  DRIFT + LOW STABILITY — PERSONA.md update recommended.")
        if args.apply:
            apply_to_persona(dna_tag)
        else:
            try:
                ans = input(f"  Apply [{dna_tag}] to PERSONA.md? (y/N) ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                ans = ""
            if ans == "y":
                apply_to_persona(dna_tag)
    elif drift:
        print("ℹ️  Drift detected but stability is acceptable. Monitor over next sessions.")


if __name__ == "__main__":
    main()
