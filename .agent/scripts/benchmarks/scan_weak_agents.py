#!/usr/bin/env python3
"""
Universal Agent Quality Scanner
Ranks all agent .md files by quality score and shows the weakest ones.
Can also run as a CI gate: fails with exit code 1 if any agent is below threshold.

Scoring Dimensions (each 0-10):
  1. Size          - File has meaningful content (too small = stub)
  2. Mandate       - Has a core mandate / goal statement
  3. Workflow      - Has a defined workflow or step list
  4. Skills        - References at least one skill in frontmatter
  5. Precision     - Contains numeric thresholds, rules, or constraints
  6. Edge Cases    - Has edge cases, warnings, or escalation logic
  7. Output Format - Defines expected output format or schema

Usage:
  python3 scan_weak_agents.py [agents_root_dir] [--top N]
  python3 scan_weak_agents.py [agents_root_dir] --gate [--min-score 60]

Gate Mode:
  --gate        Exit with code 1 if any agent is below --min-score threshold.
  --min-score N Minimum acceptable score percentage (default: 50).
                Agents below this score block the gate.
"""

import sys
import re
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple
import argparse


@dataclass
class AgentScore:
    path: Path
    name: str
    size_bytes: int
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
    # (key, label, pattern, max_pts, description)
    ("size",        "Size",         None,                                   10, "File is substantive (> 500 bytes = 5pts, > 1500 = 10pts)"),
    ("mandate",     "Mandate",      r"mandate|objective|goal|purpose|mission|primary\s+role", 10, "Clear core mandate"),
    ("workflow",    "Workflow",     r"workflow|procedure|step\s+\d|##\s+\d|^\d+\.\s+\*\*",    10, "Defined workflow/steps"),
    ("skills",      "Skills",       r"^skills:\s*\S",                       10, "References skills in frontmatter"),
    ("precision",   "Precision",    r"\d+\s*%|\d+\s*lines|\d+\s*times|\d+\s*second|threshold|limit",  10, "Numeric thresholds or constraints"),
    ("edge_cases",  "Edge Cases",   r"edge\s*case|escalat|fallback|warning|if.*fail|exception|smoke", 10, "Edge cases / escalation logic"),
    ("output_fmt",  "Output",       r"json|yaml|schema|format|verdict|emit|output|report|returns", 10, "Defined output format"),
]


def score_agent(path: Path) -> AgentScore:
    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        content = ""

    size = len(content.encode("utf-8"))
    name = path.stem

    scores = {}

    # Size scoring
    if size > 3000:
        scores["size"] = 10
    elif size > 1500:
        scores["size"] = 8
    elif size > 800:
        scores["size"] = 5
    elif size > 300:
        scores["size"] = 2
    else:
        scores["size"] = 0

    # Pattern-based scoring
    for key, label, pattern, max_pts, _ in CHECKS:
        if key == "size":
            continue
        if pattern and re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
            scores[key] = max_pts
        else:
            scores[key] = 0

    total = sum(scores.values())
    max_total = sum(pts for _, _, _, pts, _ in CHECKS)
    return AgentScore(path, name, size, scores, total, max_total)


def scan_agents(root: Path) -> List[AgentScore]:
    results = []
    for md_file in root.rglob("*.md"):
        score = score_agent(md_file)
        results.append(score)
    return sorted(results, key=lambda x: x.total)


def print_agent_detail(agent: AgentScore, rank: int) -> None:
    rel = agent.path.relative_to(
        agent.path.parents[agent.path.parts.index(".agent") - 1]
        if ".agent" in agent.path.parts else agent.path.parent
    )
    print(f"\n{'─'*60}")
    print(f"  #{rank}  {agent.grade}  [{agent.name}]")
    print(f"  Path:  {agent.path}")
    print(f"  Size:  {agent.size_bytes} bytes  |  Score: {agent.total}/{agent.max_total} ({agent.pct:.0f}%)")
    print(f"  {'Dimension':<14} {'Score':>6}  {'Bar'}")
    print(f"  {'─'*40}")
    for key, label, _, max_pts, _ in CHECKS:
        s = agent.scores.get(key, 0)
        bar = "█" * s + "░" * (max_pts - s)
        missing = "" if s > 0 else "  ← MISSING"
        print(f"  {label:<14} {s:>3}/{max_pts}  [{bar}]{missing}")


def main():
    parser = argparse.ArgumentParser(
        description="Rank agents by quality score. Use --gate for CI enforcement."
    )
    parser.add_argument("root", nargs="?",
                        default=None,
                        help="Agents root dir OR project root containing .agent/agents/")
    parser.add_argument("--top", type=int, default=5,
                        help="Number of weakest agents to show in report (default: 5)")
    parser.add_argument("--gate", action="store_true",
                        help="Gate mode: exit 1 if any agent is below --min-score")
    parser.add_argument("--min-score", type=int, default=50, dest="min_score",
                        help="Minimum acceptable score %% in gate mode (default: 50)")
    args = parser.parse_args()

    # Resolve path: support project root (contains .agent/agents/) or direct agents dir
    raw = Path(args.root) if args.root else Path.cwd()
    if (raw / ".agent" / "agents").is_dir():
        root = raw / ".agent" / "agents"
    elif raw.is_dir():
        root = raw
    else:
        print(f"ERROR: Cannot resolve agents directory from: {raw}")
        sys.exit(1)

    if not root.exists():
        print(f"ERROR: Directory not found: {root}")
        sys.exit(1)

    agents = scan_agents(root)
    total_agents = len(agents)

    # ── Gate Mode ──────────────────────────────────────────────
    if args.gate:
        violations = [a for a in agents if a.pct < args.min_score]
        print(f"\n{'='*60}")
        print(f"  Agent Quality Gate  (min-score: {args.min_score}%)")
        print(f"  Scanned: {total_agents} agents")
        print(f"{'='*60}")
        if violations:
            print(f"\n  ❌ GATE FAILED — {len(violations)} agent(s) below threshold:\n")
            for a in violations:
                print(f"  • {a.name:<32} {a.total}/{a.max_total} ({a.pct:.0f}%)  {a.grade}")
                missing = [label for key, label, *_ in CHECKS if a.scores.get(key, 0) == 0]
                if missing:
                    print(f"    Missing: {', '.join(missing)}")
            print(f"\n  Fix the agents above and re-run the gate.")
            print(f"{'='*60}\n")
            sys.exit(1)
        else:
            print(f"\n  ✅ GATE PASSED — all {total_agents} agents score ≥ {args.min_score}%")
            print(f"{'='*60}\n")
            sys.exit(0)

    # ── Report Mode ─────────────────────────────────────────────
    weakest = agents[:args.top]

    print(f"\n{'='*60}")
    print(f"  Agent Quality Scan — {total_agents} agents found")
    print(f"  Showing {args.top} WEAKEST agents")
    print(f"{'='*60}")

    for i, agent in enumerate(weakest, 1):
        print_agent_detail(agent, i)

    print(f"\n{'='*60}")
    print(f"  Full Ranking (all {total_agents} agents):\n")
    print(f"  {'Rank':<5} {'Score':>7} {'Grade':<12} {'Agent'}")
    print(f"  {'─'*55}")
    for i, a in enumerate(agents, 1):
        marker = " ← WEAKEST" if i <= args.top else ""
        print(f"  {i:<5} {a.total:>3}/{a.max_total} ({a.pct:>3.0f}%)  {a.grade:<12}  {a.name}{marker}")

    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    main()
