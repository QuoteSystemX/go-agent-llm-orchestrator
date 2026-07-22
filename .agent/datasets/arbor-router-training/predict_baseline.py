#!/usr/bin/env python3
"""Baseline predictor for the router-training dataset.

Uses the existing rule-based router in .agent/config/router_rules.json:
scores each task via keyword weights + failure-context bonus, then maps
the score to a tier via the configured thresholds.

Usage:
    python3 predict_baseline.py --split B_dev --out predictions.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

DATASET_DIR = Path(__file__).resolve().parent
REPO_ROOT = DATASET_DIR.parents[2]
RULES_PATH = REPO_ROOT / ".agent" / "config" / "router_rules.json"


def score_task(text: str, scoring: dict) -> int:
    lowered = text.lower()
    total = scoring.get("base_score", 5)
    for kw, weight in scoring.get("weights", {}).items():
        if kw.startswith("_"):
            continue
        if kw in lowered:
            total += weight

    fc = scoring.get("failure_context", {})
    bonus = 0
    for kw in fc.get("keywords", []):
        if kw in lowered:
            bonus += 1
    total += min(bonus, fc.get("max_bonus", 0))
    return total


def bucket(score: int, thresholds: dict) -> str:
    # thresholds are lower bounds; a score >= threshold[Lx] lands in that tier.
    ordered = sorted(thresholds.items(), key=lambda kv: kv[1])
    tier = ordered[0][0]
    for name, thr in ordered:
        if score >= thr:
            tier = name
    # cap at L4 (dataset uses L1..L4)
    return tier if tier in {"L1", "L2", "L3", "L4"} else "L4"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["B_dev", "B_test"], default="B_dev")
    ap.add_argument("--out", type=Path, default=DATASET_DIR / "baseline_predictions.jsonl")
    args = ap.parse_args()

    rules = json.loads(RULES_PATH.read_text())
    scoring = rules["scoring"]
    thresholds = scoring["thresholds"]

    with (DATASET_DIR / f"{args.split}.jsonl").open() as src, args.out.open("w") as dst:
        for line in src:
            row = json.loads(line)
            s = score_task(row["task"], scoring)
            dst.write(json.dumps({"id": row["id"], "predicted": bucket(s, thresholds)}) + "\n")

    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
