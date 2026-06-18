#!/usr/bin/env python3
"""
DNA Git Analyzer — objective DNA profiling from git commit history.

Parses git log, maps metrics to the same 6 axes as dna_questions.json,
and produces a DNA tag consistent with the onboarding wizard. No LLM required.

Usage:
    python dna_git_analyzer.py                      # analyze current user
    python dna_git_analyzer.py --author "Name"      # specific author
    python dna_git_analyzer.py --apply              # auto-write to PERSONA.md
    python dna_git_analyzer.py --since 2025-01-01   # limit history window
"""

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / ".agent" / "scripts"
CONFIG_PATH = REPO_ROOT / ".agent" / "config" / "dna_questions.json"
OUTPUT_PATH = REPO_ROOT / ".agent" / "bus" / "dna_git_analysis.json"
PERSONA_FILE = REPO_ROOT / ".agent" / "rules" / "PERSONA.md"
DNA_BUS_FILE = REPO_ROOT / ".agent" / "bus" / "user_dna.json"

# Mirrors dna_questions.json axes for consistent DNA tags
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

_TYPE_RE = re.compile(
    r"^(feat|fix|refactor|chore|docs|test|style|perf|build|ci)[\(:]", re.IGNORECASE
)
_TEST_PATH_RE = re.compile(r"test|spec", re.IGNORECASE)
_DOC_EXT_RE = re.compile(r"\.(md|rst|txt|adoc)$", re.IGNORECASE)


# ── Git parsing ───────────────────────────────────────────────────────────────

def _default_author() -> str:
    r = subprocess.run(["git", "config", "user.name"], capture_output=True, text=True)
    return r.stdout.strip() or "unknown"


def parse_git_log(author: str, since: str | None = None) -> list[dict]:
    """Return list of {hash, message, files} dicts for the given author."""
    cmd = [
        "git", "log", "--all",
        f"--author={author}",
        "--diff-filter=AM",
        "--name-only",
        "--format=COMMIT:%H|%s",
    ]
    if since:
        cmd.append(f"--since={since}")

    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        return []

    commits: list[dict] = []
    current: dict | None = None
    for line in r.stdout.splitlines():
        if line.startswith("COMMIT:"):
            if current is not None:
                commits.append(current)
            _, rest = line.split(":", 1)
            hash_, msg = rest.split("|", 1) if "|" in rest else (rest, "")
            current = {"hash": hash_.strip(), "message": msg.strip(), "files": []}
        elif line.strip() and current is not None:
            current["files"].append(line.strip())
    if current is not None:
        commits.append(current)
    return commits


# ── Metrics ───────────────────────────────────────────────────────────────────

def compute_metrics(commits: list[dict]) -> dict:
    """Aggregate raw git metrics from parsed commits."""
    if not commits:
        return {"total_commits": 0}

    total = len(commits)
    all_files = [f for c in commits for f in c["files"]]
    total_files = len(all_files) or 1

    avg_files = len(all_files) / total

    test_files = sum(1 for f in all_files if _TEST_PATH_RE.search(f))
    test_ratio = test_files / total_files

    doc_files = sum(1 for f in all_files if _DOC_EXT_RE.search(f) or "doc" in f.lower())
    comment_density = doc_files / total_files

    type_counts: Counter = Counter()
    keyword_counts: Counter = Counter()
    for c in commits:
        msg = c["message"]
        m = _TYPE_RE.match(msg)
        if m:
            type_counts[m.group(1).lower()] += 1
        msg_l = msg.lower()
        for kw in ("fix", "simplify", "refactor", "extract", "hack", "wip", "cleanup"):
            if kw in msg_l:
                keyword_counts[kw] += 1

    return {
        "total_commits": total,
        "avg_files_per_commit": round(avg_files, 2),
        "test_ratio": round(test_ratio, 3),
        "comment_density": round(comment_density, 3),
        "commit_types": dict(type_counts),
        "msg_keywords": dict(keyword_counts),
    }


# ── Weighted signal fusion ────────────────────────────────────────────────────

def score_axes(metrics: dict) -> dict[str, float]:
    """Map git metrics to axis scores via weighted signal fusion."""
    scores: dict[str, float] = {k: 0.0 for axis in AXES.values() for k in axis}
    total = max(metrics.get("total_commits", 1), 1)
    types = metrics.get("commit_types", {})
    kw = metrics.get("msg_keywords", {})

    feat_pct = types.get("feat", 0) / total
    fix_pct = types.get("fix", 0) / total
    refactor_pct = types.get("refactor", 0) / total
    chore_docs_pct = (types.get("chore", 0) + types.get("docs", 0)) / total

    avg_files: float = metrics.get("avg_files_per_commit", 0)
    test_ratio: float = metrics.get("test_ratio", 0)
    comment_density: float = metrics.get("comment_density", 0)

    hack_n = kw.get("hack", 0) + kw.get("wip", 0)
    simplify_n = kw.get("simplify", 0) + kw.get("cleanup", 0)
    refactor_n = kw.get("refactor", 0) + kw.get("extract", 0)

    # feat-heavy + broad scope → creative / code-first (exploratory style)
    if feat_pct > 0.35:
        scores["creative"] += 3.0 * feat_pct
        scores["codefirst"] += 2.0 * feat_pct

    # fix-heavy → pragmatic (reactive, not over-engineered)
    if fix_pct > 0.25:
        scores["pragmatic"] += 3.0 * fix_pct

    # small commits → minimal / pragmatic (focused, atomic changes)
    if avg_files < 3:
        scores["pragmatic"] += 1.5
        scores["minimal"] += 1.5
    elif avg_files > 6:
        # large commits → creative (feature-breadth) or clean (big refactors)
        scores["creative"] += 1.0

    # refactor commit type or keywords → clean / structured
    refactor_signal = max(refactor_pct, refactor_n / total)
    if refactor_signal > 0.1:
        scores["clean"] += 3.0 * refactor_signal

    # high test ratio → TDD signal
    if test_ratio > 0.20:
        scores["tdd"] += 3.0 * test_ratio
    elif test_ratio < 0.08:
        scores["minimal"] += 1.5  # minimal testing style
        scores["codefirst"] += 0.5

    # simplify/cleanup keywords → minimal
    if simplify_n > 2:
        scores["minimal"] += min(2.0, simplify_n * 0.3)
        scores["pragmatic"] += min(1.0, simplify_n * 0.15)

    # hack/wip → creative (rapid prototyping)
    if hack_n > 1:
        scores["creative"] += min(2.0, hack_n * 0.5)

    # documentation/chore density → clean / structured
    if comment_density > 0.08:
        scores["clean"] += 2.0 * comment_density
    if chore_docs_pct > 0.15:
        scores["clean"] += 1.0

    # fallback: sparse signal → default to pragmatic/minimal
    if all(v < 0.3 for v in scores.values()):
        scores["pragmatic"] += 1.0
        scores["minimal"] += 0.5

    return {k: round(v, 3) for k, v in scores.items()}


def compute_dna(scores: dict[str, float]) -> tuple[str, str]:
    primary = max(AXES["primary"], key=lambda k: scores.get(k, 0.0))
    secondary = max(AXES["secondary"], key=lambda k: scores.get(k, 0.0))
    return DNA_LABELS[primary], DNA_LABELS[secondary]


def compute_confidence(scores: dict[str, float], metrics: dict) -> float:
    """Confidence based on signal coverage, axis dominance, and commit count."""
    non_zero = sum(1 for v in scores.values() if v > 0.3)
    coverage = non_zero / len(scores)

    def _dominance(keys: list[str]) -> float:
        vals = sorted((scores.get(k, 0.0) for k in keys), reverse=True)
        if vals[0] == 0:
            return 0.0
        return min(1.0, (vals[0] - vals[1]) / vals[0]) if len(vals) > 1 else 1.0

    dominance = (_dominance(AXES["primary"]) + _dominance(AXES["secondary"])) / 2
    count_factor = min(1.0, metrics.get("total_commits", 0) / 50)

    raw = 0.35 * coverage + 0.45 * dominance + 0.20 * count_factor
    return round(min(0.99, max(0.10, raw)), 2)


# ── Discrepancy check ─────────────────────────────────────────────────────────

def check_discrepancy(detected_tag: str, bus_file: Path = DNA_BUS_FILE) -> str | None:
    """Return wizard's DNA tag if it differs from detected, else None."""
    if not bus_file.exists():
        return None
    try:
        data = json.loads(bus_file.read_text(encoding="utf-8"))
        wizard = data.get("dna", "")
        return wizard if wizard and wizard != detected_tag else None
    except Exception:
        return None


# ── PERSONA.md writer ─────────────────────────────────────────────────────────

def _load_profile(dna_tag: str) -> str:
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        profiles = config.get("profiles", {})
        profile = profiles.get(dna_tag, profiles.get("BALANCED", {}))
        stylistic = "\n".join(f"- {s}" for s in profile.get("stylistic", []))
        philosophy = "\n".join(f"- {p}" for p in profile.get("philosophy", []))
    except Exception:
        stylistic = "- Adapt to context."
        philosophy = "- Pragmatic default: choose the simplest approach that works."

    return f"""\
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


def apply_to_persona(dna_tag: str) -> None:
    content = _load_profile(dna_tag)
    PERSONA_FILE.write_text(content, encoding="utf-8")
    print(f"✅ PERSONA.md updated → [{dna_tag}]")

    adapter = SCRIPTS_DIR / "orchestration" / "personality_adapter.py"
    try:
        import subprocess as _sp
        _sp.run([sys.executable, str(adapter)], check=True)
        print("✅ personality_adapter synced user_dna.json")
    except Exception as exc:
        print(f"⚠️  personality_adapter failed: {exc}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="DNA Git Analyzer — objective DNA from git history")
    parser.add_argument("--author", default=None, help="Git author name (default: git config user.name)")
    parser.add_argument("--apply", action="store_true", help="Auto-write detected DNA to PERSONA.md")
    parser.add_argument("--since", default=None, help="Limit history: e.g. 2025-01-01")
    args = parser.parse_args()

    author = args.author or _default_author()
    print(f"🔍 Analyzing git history for: {author}")

    commits = parse_git_log(author, since=args.since)
    if not commits:
        print(f"⚠️  No commits found for author '{author}'. Check --author value.")
        sys.exit(0)

    metrics = compute_metrics(commits)
    scores = score_axes(metrics)
    primary, secondary = compute_dna(scores)
    dna_tag = f"{primary} / {secondary}"
    confidence = compute_confidence(scores, metrics)

    print(f"\n📊 Metrics ({metrics['total_commits']} commits):")
    print(f"   avg files/commit : {metrics['avg_files_per_commit']}")
    print(f"   test ratio       : {metrics['test_ratio']:.1%}")
    print(f"   comment density  : {metrics['comment_density']:.1%}")
    print(f"   commit types     : {metrics.get('commit_types', {})}")
    print(f"   keywords         : {metrics.get('msg_keywords', {})}")

    print(f"\n🧬 Detected DNA: [{dna_tag}]  (confidence: {confidence:.0%})")

    discrepancy = check_discrepancy(dna_tag)
    if discrepancy:
        print(f"⚠️  Discrepancy: wizard set [{discrepancy}], git analysis suggests [{dna_tag}]")
        print("   Consider re-running the onboarding wizard or using --apply to override.")

    # Save analysis to bus
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "author": author,
        "commits_analyzed": metrics["total_commits"],
        "metrics": metrics,
        "axis_scores": scores,
        "detected_dna": f"[{dna_tag}]",
        "confidence": confidence,
        "wizard_dna": discrepancy,
    }
    OUTPUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n💾 Report saved → {OUTPUT_PATH.relative_to(REPO_ROOT)}")

    if args.apply:
        apply_to_persona(dna_tag)
    else:
        try:
            answer = input(f"\nApply [{dna_tag}] to PERSONA.md? (y/N) ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = ""
        if answer == "y":
            apply_to_persona(dna_tag)
        else:
            print("ℹ️  PERSONA.md unchanged. Run with --apply to skip this prompt.")


if __name__ == "__main__":
    main()
