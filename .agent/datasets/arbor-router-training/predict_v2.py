#!/usr/bin/env python3
"""v2 predictor: phrase-first routing + expanded vocabulary.

Checks rules[].keywords multi-word phrases (L4 → L1) before falling
back to weighted scoring from router_rules.json.

Usage:
    python3 predict_v2.py --split B_dev --out predictions_v2_dev.jsonl
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

DATASET_DIR = Path(__file__).resolve().parent
REPO_ROOT = DATASET_DIR.parents[2]
RULES_PATH = REPO_ROOT / ".agent" / "config" / "router_rules.json"

TIER_ORDER = {"L4": 4, "L3": 3, "L2": 2, "L1": 1}


def phrase_match(text: str, rules: list[dict]) -> str | None:
    """Return the complexity tier of the first matching phrase rule (L4 first), or None."""
    sorted_rules = sorted(rules, key=lambda r: TIER_ORDER.get(r["complexity"], 0), reverse=True)
    for rule in sorted_rules:
        for kw in rule.get("keywords", []):
            if " " in kw and kw in text:
                return rule["complexity"]
    return None


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
    ordered = sorted(thresholds.items(), key=lambda kv: kv[1])
    tier = ordered[0][0]
    for name, thr in ordered:
        if score >= thr:
            tier = name
    return tier if tier in {"L1", "L2", "L3", "L4"} else "L4"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["B_dev", "B_test"], default="B_dev")
    ap.add_argument("--out", type=Path, default=DATASET_DIR / "predictions_v2.jsonl")
    args = ap.parse_args()

    rules_data = json.loads(RULES_PATH.read_text())
    scoring = rules_data["scoring"]
    thresholds = scoring["thresholds"]
    rules = rules_data.get("rules", [])

    with (DATASET_DIR / f"{args.split}.jsonl").open() as src, args.out.open("w") as dst:
        for line in src:
            row = json.loads(line)
            lowered = row["task"].lower()

            tier = phrase_match(lowered, rules)
            if tier is None:
                s = score_task(row["task"], scoring)
                tier = bucket(s, thresholds)

            dst.write(json.dumps({"id": row["id"], "predicted": tier}) + "\n")

    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
