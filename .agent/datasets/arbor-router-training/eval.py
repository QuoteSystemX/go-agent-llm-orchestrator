#!/usr/bin/env python3
"""Arbor router-training evaluator.

Reads a predictions JSONL and prints a single-line score plus a JSON block.

Usage:
    python3 eval.py --split B_dev --predictions predictions.jsonl
    python3 eval.py --split B_test --predictions predictions.jsonl

Predictions schema (one JSON object per line):
    {"id": "dev-001", "predicted": "L2"}

Score:
    per_example = 1 - 0.15 * overshoot - 0.35 * undershoot   (clamped to [0, 1])
        overshoot  = max(0, tier_idx(pred) - tier_idx(true))   # cost waste
        undershoot = max(0, tier_idx(true) - tier_idx(pred))   # quality risk
    score = mean(per_example)         # direction: maximize
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

TIER_IDX = {"L1": 1, "L2": 2, "L3": 3, "L4": 4}
DATASET_DIR = Path(__file__).resolve().parent


def load_jsonl(path: Path) -> list[dict]:
    with path.open() as fh:
        return [json.loads(line) for line in fh if line.strip()]


def score_predictions(gold: list[dict], preds: list[dict]) -> dict:
    by_id = {p["id"]: p for p in preds}
    missing = [g["id"] for g in gold if g["id"] not in by_id]
    if missing:
        raise SystemExit(f"predictions missing for ids: {missing[:5]}... ({len(missing)} total)")

    per_example, correct = [], 0
    confusion: dict[str, dict[str, int]] = {t: {t2: 0 for t2 in TIER_IDX} for t in TIER_IDX}
    for g in gold:
        true = g["label"]
        pred = by_id[g["id"]]["predicted"]
        if pred not in TIER_IDX:
            raise SystemExit(f"invalid predicted tier {pred!r} for id={g['id']}")
        over = max(0, TIER_IDX[pred] - TIER_IDX[true])
        under = max(0, TIER_IDX[true] - TIER_IDX[pred])
        per = max(0.0, 1.0 - 0.15 * over - 0.35 * under)
        per_example.append(per)
        confusion[true][pred] += 1
        if pred == true:
            correct += 1

    n = len(gold)
    return {
        "n": n,
        "accuracy": round(correct / n, 4),
        "score": round(sum(per_example) / n, 4),
        "confusion": confusion,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["B_dev", "B_test"], default="B_dev")
    ap.add_argument("--predictions", required=True, type=Path)
    args = ap.parse_args()

    gold = load_jsonl(DATASET_DIR / f"{args.split}.jsonl")
    preds = load_jsonl(args.predictions)
    result = score_predictions(gold, preds)

    # Machine-parseable: the arbor coordinator scrapes this line.
    print(f"score: {result['score']}")
    json.dump(result, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
