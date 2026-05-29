#!/usr/bin/env python3
"""
DNA Auto-Adapt Orchestrator — unifies phases 1-3 into a single pipeline.

Pipeline: Onboarding → Git Analyzer → Session Learner → Merge → Apply → Log.
Each phase is atomic (try/except); failures are logged, others continue.

Usage:
    python dna_orchestrator.py                        # semi mode (y/N prompts)
    python dna_orchestrator.py --mode=auto            # apply silently
    python dna_orchestrator.py --mode=manual          # show only, no writes
    python dna_orchestrator.py --dry-run              # show changes without writing
    python dna_orchestrator.py --phases=2,3           # run specific phases
    python dna_orchestrator.py --interval=5           # skip if <5 sessions since last run
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / ".agent" / "scripts"
BUS = REPO_ROOT / ".agent" / "bus"
CONFIG_PATH = REPO_ROOT / ".agent" / "config" / "dna_questions.json"
PERSONA_FILE = REPO_ROOT / ".agent" / "rules" / "PERSONA.md"
DNA_BUS_FILE = BUS / "user_dna.json"
EVOLUTION_LOG = BUS / "dna_evolution_log.json"

PRIMARY_AXES = ["clean", "pragmatic", "creative"]
SECONDARY_AXES = ["tdd", "codefirst", "minimal"]
ALL_AXES = PRIMARY_AXES + SECONDARY_AXES
DNA_LABELS = {
    "clean": "ARCHITECT", "pragmatic": "PRAGMATIC", "creative": "VISIONARY",
    "tdd": "TDD", "codefirst": "CODE-FIRST", "minimal": "MINIMALIST",
}


# ── Phase runners ─────────────────────────────────────────────────────────────

def _phase_onboarding(dry_run: bool) -> dict:
    """Phase 1: run onboarding wizard only if user_dna.json is missing."""
    if DNA_BUS_FILE.exists():
        try:
            data = json.loads(DNA_BUS_FILE.read_text())
            tag = data.get("dna", "BALANCED")
            return {"tag": tag, "confidence": 0.5, "axis_scores": {}, "reason": "already onboarded", "skipped": True}
        except Exception:
            pass

    if dry_run:
        return {"tag": "BALANCED", "confidence": 0.3, "axis_scores": {},
                "reason": "would run onboarding wizard (user_dna.json missing)", "skipped": False}

    # Launch wizard with subprocess (requires interactive terminal)
    import subprocess
    wizard = SCRIPTS_DIR / "orchestration" / "dna_onboarder.py"
    result = subprocess.run([sys.executable, str(wizard)], check=False)
    if result.returncode == 0 and DNA_BUS_FILE.exists():
        data = json.loads(DNA_BUS_FILE.read_text())
        return {"tag": data.get("dna", "BALANCED"), "confidence": 0.8,
                "axis_scores": {}, "reason": "wizard completed", "skipped": False}
    return {"tag": "BALANCED", "confidence": 0.3, "axis_scores": {},
            "reason": "wizard skipped or failed", "skipped": True}


def _phase_git(dry_run: bool) -> dict:
    """Phase 2: git history analysis → axis_scores + confidence."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    from orchestration.dna_git_analyzer import (  # type: ignore[import]
        _default_author, parse_git_log, compute_metrics, score_axes, compute_dna, compute_confidence,
    )
    author = _default_author()
    commits = parse_git_log(author)
    if not commits:
        return {"tag": "BALANCED", "confidence": 0.1, "axis_scores": {},
                "reason": f"no commits found for {author}", "skipped": True}

    metrics = compute_metrics(commits)
    scores = score_axes(metrics)
    primary, secondary = compute_dna(scores)
    tag = f"{primary} / {secondary}"
    confidence = compute_confidence(scores, metrics)
    reason = (
        f"{metrics['total_commits']} commits | "
        f"avg {metrics['avg_files_per_commit']} files | "
        f"test_ratio {metrics['test_ratio']:.0%}"
    )
    return {"tag": tag, "confidence": confidence, "axis_scores": scores, "reason": reason, "skipped": False}


def _phase_session(dry_run: bool) -> dict:
    """Phase 3: session learner → axis_scores + stability."""
    from orchestration.dna_session_learner import (  # type: ignore[import]
        _load_telemetry_events, _load_output_goals, _load_git_scores, _load_history,
        score_from_telemetry, score_from_outputs, fuse_scores, compute_dna as _cdna,
        compute_stability, drift_immediate, drift_rolling,
    )
    events = _load_telemetry_events()
    goals = _load_output_goals()
    git_scores = _load_git_scores()
    history = _load_history()

    if not events and not goals:
        return {"tag": "BALANCED", "confidence": 0.1, "axis_scores": {},
                "reason": "no session data available", "skipped": True}

    t = score_from_telemetry(events)
    o = score_from_outputs(goals)
    fused = fuse_scores(t, o, git_scores)
    tag = _cdna(fused)  # returns full "PRIMARY / SECONDARY" string
    stability = compute_stability(t, o, git_scores, history)
    prev = history[-1] if history else None
    drift = drift_immediate(fused, prev) or drift_rolling(history)
    reason = f"{len(events)} routing events | {len(goals)} goals | stability={stability:.2f} | drift={drift}"
    return {"tag": tag, "confidence": stability, "axis_scores": fused, "reason": reason, "skipped": False}


PHASE_REGISTRY = {
    1: {"name": "Onboarding",     "fn": _phase_onboarding},
    2: {"name": "Git Analyzer",   "fn": _phase_git},
    3: {"name": "Session Learner","fn": _phase_session},
}


# ── DNA merge ─────────────────────────────────────────────────────────────────

def merge_dna(results: list[dict]) -> tuple[str, float, dict]:
    """Confidence-weighted axis_scores → recompute DNA tag."""
    active = [r for r in results if not r.get("skipped") and r.get("axis_scores")]
    if not active:
        # Fallback: highest confidence winner
        best = max(results, key=lambda r: r.get("confidence", 0))
        return best["tag"], best.get("confidence", 0.3), {}

    total_conf = sum(r["confidence"] for r in active)
    if total_conf == 0:
        total_conf = 1.0

    merged: dict[str, float] = {k: 0.0 for k in ALL_AXES}
    for r in active:
        w = r["confidence"] / total_conf
        for axis, score in r["axis_scores"].items():
            merged[axis] = merged.get(axis, 0.0) + w * score

    primary = max(PRIMARY_AXES, key=lambda k: merged.get(k, 0.0))
    secondary = max(SECONDARY_AXES, key=lambda k: merged.get(k, 0.0))
    tag = f"{DNA_LABELS[primary]} / {DNA_LABELS[secondary]}"
    avg_conf = round(sum(r["confidence"] for r in active) / len(active), 3)
    return tag, avg_conf, {k: round(v, 3) for k, v in merged.items()}


# ── PERSONA.md writer ─────────────────────────────────────────────────────────

def _write_persona(dna_tag: str) -> None:
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        profiles = config.get("profiles", {})
        profile = profiles.get(dna_tag, profiles.get("BALANCED", {}))
        stylistic = "\n".join(f"- {s}" for s in profile.get("stylistic", ["- Adapt to context."]))
        philosophy = "\n".join(f"- {p}" for p in profile.get("philosophy", ["- Pragmatic default."]))
    except Exception:
        stylistic = "- Adapt to context."
        philosophy = "- Pragmatic default."

    PERSONA_FILE.write_text(
        f"# User Personality Profile (DNA) 🎭\n\n"
        f"This document defines the preferred communication style, technical depth, and coding philosophy.\n\n"
        f"## 🧬 Core DNA: [{dna_tag}]\n\n"
        f"### 🛰️ Stylistic Preferences\n\n{stylistic}\n\n"
        f"### 🛠️ Technical Philosophy\n\n{philosophy}\n\n"
        f"---\n> [!NOTE]\n> This profile is automatically read by `personality_adapter.py`.\n",
        encoding="utf-8",
    )


# ── Evolution log ─────────────────────────────────────────────────────────────

def _append_evolution_event(
    phase_name: str, prev_tag: str, new_tag: str, confidence: float,
    reason: str, mode: str, approved: bool,
) -> None:
    try:
        log = json.loads(EVOLUTION_LOG.read_text()) if EVOLUTION_LOG.exists() else {"events": []}
    except Exception:
        log = {"events": []}
    log["events"].append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": phase_name,
        "previous_dna": prev_tag,
        "new_dna": new_tag,
        "confidence": confidence,
        "reason": reason,
        "mode": mode,
        "user_approved": approved,
    })
    EVOLUTION_LOG.write_text(json.dumps(log, indent=2), encoding="utf-8")


# ── Interval check ────────────────────────────────────────────────────────────

def _should_skip_interval(interval: int) -> bool:
    """Return True if fewer than `interval` sessions have run since last orchestration."""
    if interval <= 0:
        return False
    try:
        log = json.loads(EVOLUTION_LOG.read_text()) if EVOLUTION_LOG.exists() else {"events": []}
        events = log.get("events", [])
        if not events:
            return False
        # Count bus/outputs entries since last orchestration timestamp
        last_ts = events[-1].get("timestamp", "")
        outputs_dir = BUS / "outputs"
        if not outputs_dir.exists():
            return False
        sessions_since = sum(
            1 for f in outputs_dir.glob("*.json")
            if f.stem > last_ts[:15].replace("-", "").replace("T", "_").replace(":", "")
        )
        return sessions_since < interval
    except Exception:
        return False


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="DNA Auto-Adapt Orchestrator")
    parser.add_argument("--mode", choices=["manual", "semi", "auto"], default="semi")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--phases", default="1,2,3", help="Comma-separated phase IDs to run")
    parser.add_argument("--interval", type=int, default=0,
                        help="Skip if fewer than N sessions since last run")
    args = parser.parse_args()

    if _should_skip_interval(args.interval):
        print(f"⏭️  Skipping — fewer than {args.interval} sessions since last orchestration.")
        return

    try:
        phase_ids = [int(x.strip()) for x in args.phases.split(",")]
    except ValueError:
        print(f"❌ Invalid --phases value: {args.phases}")
        sys.exit(1)

    phases_to_run = {pid: PHASE_REGISTRY[pid] for pid in phase_ids if pid in PHASE_REGISTRY}
    if not phases_to_run:
        print("❌ No valid phases selected.")
        sys.exit(1)

    print(f"\n🧬 DNA Auto-Adapt Orchestrator  [mode={args.mode}{'  dry-run' if args.dry_run else ''}]")
    print(f"   Running phases: {list(phases_to_run.keys())}\n")

    # Read current DNA
    prev_tag = "BALANCED"
    try:
        prev_tag = json.loads(DNA_BUS_FILE.read_text()).get("dna", "BALANCED")
    except Exception as e:
        logger.error("[dna_orchestrator] Failed to load previous DNA tag: %s", e, exc_info=True)
        raise

    results: list[dict] = []
    for pid, phase in phases_to_run.items():
        print(f"── Phase {pid}: {phase['name']} ──")
        try:
            result = phase["fn"](dry_run=args.dry_run)
            status = "⏭️  skipped" if result.get("skipped") else f"🧬 [{result['tag']}] conf={result['confidence']:.2f}"
            print(f"   {status}")
            print(f"   reason: {result.get('reason', '')}")
            results.append(result)
        except Exception as exc:
            print(f"   ⚠️  Phase {pid} failed: {exc}")
            results.append({"tag": "BALANCED", "confidence": 0.0, "axis_scores": {},
                            "reason": str(exc), "skipped": True})

    if not results:
        print("❌ All phases failed.")
        sys.exit(1)

    new_tag, confidence, merged_scores = merge_dna(results)
    print(f"\n{'── MERGE ──':─<40}")
    print(f"   Previous DNA : [{prev_tag}]")
    print(f"   Merged DNA   : [{new_tag}]  (confidence={confidence:.2f})")
    reason = " | ".join(r.get("reason", "") for r in results if not r.get("skipped"))

    if args.mode == "manual" or args.dry_run:
        print(f"\n{'── DRY RUN / MANUAL — no changes written ──':─<40}")
        _append_evolution_event("orchestrator", prev_tag, new_tag, confidence, reason,
                                args.mode, approved=False)
        return

    approved = False
    if args.mode == "auto":
        approved = True
    elif args.mode == "semi":
        try:
            ans = input(f"\nApply [{new_tag}] to PERSONA.md? (y/N) ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            ans = ""
        approved = ans == "y"

    if approved:
        if not args.dry_run:
            _write_persona(new_tag)
            # Update user_dna.json tag field
            try:
                existing = json.loads(DNA_BUS_FILE.read_text()) if DNA_BUS_FILE.exists() else {}
            except Exception:
                existing = {}
            existing["dna"] = new_tag
            if merged_scores:
                existing["axis_scores"] = merged_scores
            DNA_BUS_FILE.parent.mkdir(parents=True, exist_ok=True)
            DNA_BUS_FILE.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        print(f"✅ PERSONA.md updated → [{new_tag}]")
    else:
        print("ℹ️  No changes applied.")

    _append_evolution_event("orchestrator", prev_tag, new_tag, confidence, reason, args.mode, approved)
    print(f"💾 Evolution event logged → {EVOLUTION_LOG.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
