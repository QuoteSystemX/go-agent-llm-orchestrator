#!/usr/bin/env python3
"""
Universal Skill Quality Scanner
Ranks all SKILL.md files by quality score and shows the weakest ones.
Can also run as a CI gate: fails with exit code 1 if any skill is below threshold.

Scoring Dimensions (each 0-10):
  1. Size          - SKILL.md has meaningful content (too small = stub)
  2. Mandate       - Has a clear description / purpose statement
  3. Instructions  - Has actionable instructions or rules (not just descriptions)
  4. Examples      - Has code examples, tables, or patterns
  5. When-To-Use   - Defines when the skill should be triggered
  6. Anti-Patterns - Defines what NOT to do (❌ patterns, warnings, pitfalls)
  7. Scripts       - Has supporting scripts/ directory

Usage:
  python3 scan_weak_skills.py [skills_root_dir] [--top N]
  python3 scan_weak_skills.py [skills_root_dir] --gate [--min-score 50]

Gate Mode:
  --gate        Exit with code 1 if any skill is below --min-score threshold.
  --min-score N Minimum acceptable score percentage (default: 50).
"""

import sys
import re
import argparse
from pathlib import Path
from dataclasses import dataclass, field
from typing import List


# Skills to skip entirely (internal / meta directories)
SKIP_DIRS = {"archive", "scratch"}


@dataclass
class SkillScore:
    path: Path          # path to SKILL.md
    name: str           # skill directory name
    size_bytes: int
    has_scripts: bool
    scores: dict
    total: int
    max_total: int

    @property
    def pct(self) -> float:
        return (self.total / self.max_total) * 100 if self.max_total else 0.0

    @property
    def grade(self) -> str:
        p = self.pct
        if p >= 90: return "🏆 GOLD"
        if p >= 70: return "🥈 SILVER"
        if p >= 50: return "🥉 BRONZE"
        if p >= 30: return "⚠️  WEAK"
        return "❌ STUB"


CHECKS = [
    # (key, label, pattern_or_none, max_pts, description)
    ("size",         "Size",         None,
     10, "SKILL.md has substantive content (> 500 bytes = 5pts, > 2000 = 10pts)"),
    ("mandate",      "Mandate",      r"description|purpose|goal|this\s+skill|use\s+this\s+when|when\s+to\s+use",
     10, "Clear purpose / description statement"),
    ("instructions", "Instructions", r"##\s+\d|step\s+\d|\d+\.\s+\*\*|must|should|always|never|rule|enforce|require",
     10, "Actionable instructions or rules"),
    ("examples",     "Examples",     r"```|example|pattern|template|\|\s*\w.*\|",
     10, "Code examples, tables, or patterns"),
    ("when_to_use",  "When-To-Use",  r"when\s+to\s+use|trigger|activate|use\s+this|invoke\s+when|applicable",
     10, "Conditions that activate the skill"),
    ("anti_patterns","Anti-Patterns",r"❌|don'?t|avoid|never|anti.pattern|pitfall|wrong|bad\s+practice|not\s+recommended",
     10, "What NOT to do / pitfalls"),
    ("scripts",      "Scripts dir",  None,
     10, "Has supporting scripts/ directory alongside SKILL.md"),
]


def score_skill(skill_md: Path) -> SkillScore:
    skill_dir = skill_md.parent
    name = skill_dir.name

    try:
        content = skill_md.read_text(encoding="utf-8")
    except Exception:
        content = ""

    size = len(content.encode("utf-8"))
    has_scripts = (skill_dir / "scripts").is_dir()

    scores = {}

    # Size scoring
    if size > 4000:
        scores["size"] = 10
    elif size > 2000:
        scores["size"] = 8
    elif size > 800:
        scores["size"] = 5
    elif size > 300:
        scores["size"] = 2
    else:
        scores["size"] = 0

    # Scripts dir scoring
    scores["scripts"] = 10 if has_scripts else 0

    # Pattern-based scoring
    for key, label, pattern, max_pts, _ in CHECKS:
        if key in ("size", "scripts"):
            continue
        if pattern and re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
            scores[key] = max_pts
        else:
            scores[key] = 0

    total = sum(scores.values())
    max_total = sum(pts for _, _, _, pts, _ in CHECKS)
    return SkillScore(skill_md, name, size, has_scripts, scores, total, max_total)


def scan_skills(root: Path) -> List[SkillScore]:
    results = []
    for skill_md in root.rglob("SKILL.md"):
        # Skip archived/scratch dirs
        parts = set(skill_md.parts)
        if parts & SKIP_DIRS:
            continue
        score = score_skill(skill_md)
        results.append(score)
    return sorted(results, key=lambda x: x.total)


def print_skill_detail(skill: SkillScore, rank: int) -> None:
    print(f"\n{'─'*60}")
    print(f"  #{rank}  {skill.grade}  [{skill.name}]")
    print(f"  Path:  {skill.path}")
    print(f"  Size:  {skill.size_bytes} bytes  |  Scripts: {'✅' if skill.has_scripts else '❌'}  |  Score: {skill.total}/{skill.max_total} ({skill.pct:.0f}%)")
    print(f"  {'Dimension':<16} {'Score':>6}  {'Bar'}")
    print(f"  {'─'*44}")
    for key, label, _, max_pts, _ in CHECKS:
        s = skill.scores.get(key, 0)
        bar = "█" * s + "░" * (max_pts - s)
        missing = "" if s > 0 else "  ← MISSING"
        print(f"  {label:<16} {s:>3}/{max_pts}  [{bar}]{missing}")


def main():
    parser = argparse.ArgumentParser(
        description="Rank skills by quality score. Use --gate for CI enforcement."
    )
    parser.add_argument("root", nargs="?",
                        default=None,
                        help="Skills root dir OR project root containing .agent/skills/")
    parser.add_argument("--top", type=int, default=5,
                        help="Number of weakest skills to show in report (default: 5)")
    parser.add_argument("--gate", action="store_true",
                        help="Gate mode: exit 1 if any skill is below --min-score")
    parser.add_argument("--min-score", type=int, default=50, dest="min_score",
                        help="Minimum acceptable score %% in gate mode (default: 50)")
    args = parser.parse_args()

    # Resolve path: support project root (contains .agent/skills/) or direct skills dir
    raw = Path(args.root) if args.root else Path.cwd()
    if (raw / ".agent" / "skills").is_dir():
        root = raw / ".agent" / "skills"
    elif raw.is_dir():
        root = raw
    else:
        print(f"ERROR: Cannot resolve skills directory from: {raw}")
        sys.exit(1)

    if not root.exists():
        print(f"ERROR: Directory not found: {root}")
        sys.exit(1)

    skills = scan_skills(root)
    total_skills = len(skills)

    # ── Gate Mode ──────────────────────────────────────────────
    if args.gate:
        violations = [s for s in skills if s.pct < args.min_score]
        print(f"\n{'='*60}")
        print(f"  Skill Quality Gate  (min-score: {args.min_score}%)")
        print(f"  Scanned: {total_skills} skills")
        print(f"{'='*60}")
        if violations:
            print(f"\n  ❌ GATE FAILED — {len(violations)} skill(s) below threshold:\n")
            for s in violations:
                print(f"  • {s.name:<36} {s.total}/{s.max_total} ({s.pct:.0f}%)  {s.grade}")
                missing = [label for key, label, *_ in CHECKS if s.scores.get(key, 0) == 0]
                if missing:
                    print(f"    Missing: {', '.join(missing)}")
            print(f"\n  Fix the skills above and re-run the gate.")
            print(f"{'='*60}\n")
            sys.exit(1)
        else:
            print(f"\n  ✅ GATE PASSED — all {total_skills} skills score ≥ {args.min_score}%")
            print(f"{'='*60}\n")
            sys.exit(0)

    # ── Report Mode ─────────────────────────────────────────────
    weakest = skills[:args.top]

    print(f"\n{'='*60}")
    print(f"  Skill Quality Scan — {total_skills} skills found")
    print(f"  Showing {args.top} WEAKEST skills")
    print(f"{'='*60}")

    for i, skill in enumerate(weakest, 1):
        print_skill_detail(skill, i)

    print(f"\n{'='*60}")
    print(f"  Full Ranking (all {total_skills} skills):\n")
    print(f"  {'Rank':<5} {'Score':>7} {'Grade':<12} {'Skill'}")
    print(f"  {'─'*58}")
    for i, s in enumerate(skills, 1):
        marker = " ← WEAKEST" if i <= args.top else ""
        print(f"  {i:<5} {s.total:>3}/{s.max_total} ({s.pct:>3.0f}%)  {s.grade:<12}  {s.name}{marker}")

    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    main()
