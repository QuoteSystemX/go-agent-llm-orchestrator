---
run_name: router-training-run-708be80f
workflow: Arbor Squad Training
workflow_run: 708be80f
prepared_by: ai-engineer
prepared_at: 2026-07-22
---

# Arbor Contract — LLM Router Tier Classification

## Target

Directory: `.agent/datasets/arbor-router-training/` (this folder).
Repo base branch: `main`. Trunk branch for real merges: `arbor/trunk/router-training-run-708be80f`.

## Task

Given a natural-language engineering task description (English or Russian), predict the correct model-complexity tier (`L1`, `L2`, `L3`, `L4`) so the router can pick the cheapest capable model. The current production predictor is the keyword-weighted rules in `.agent/config/router_rules.json`; the squad may replace it, extend it, or train a new classifier — as long as it is a pure function `task_text → tier`.

## Metric

- **Name**: `score`
- **Command**: `python3 eval.py --split B_dev --predictions <predictions.jsonl>`
- **Direction**: maximize (range `[0, 1]`)
- **Definition**: `mean( max(0, 1 − 0.15·overshoot − 0.35·undershoot) )` where `overshoot = max(0, tier(pred) − tier(true))` (cost waste) and `undershoot = max(0, tier(true) − tier(pred))` (quality risk). Undershoots are penalized harder than overshoots because misrouting L4→L1 causes a real failure downstream.
- **Secondary observable**: `accuracy` (exact-match rate); reported alongside `score` in the same JSON block.

## Baseline anchor

Measured on the shipped rules today (see `baseline.json`):
- B_dev: `score 0.8088`, `accuracy 0.425`
- B_test: `score 0.795`, `accuracy 0.55`

## Ambition

Beat the baseline `score` on **B_dev** by at least **+0.05** without dropping **B_test accuracy** below the baseline (`0.55`). Stretch goal: reach `score ≥ 0.90` on both splits.

## Scope preference

Effect-leaning. Prefer changes that verifiably move the metric on B_dev over novel architectural rewrites. Rule-tuning, learned classifiers, and better feature extraction (e.g. embedding-based nearest-neighbor over labeled examples) are all in scope.

## Dev/test discipline

- Iterate freely on `B_dev.jsonl`. Never touch `B_test.jsonl` — reading it is fine, tuning on it is not.
- Baseline predictions on both splits are checkpointed under `baseline_dev.jsonl` / `baseline_test.jsonl` — do not overwrite. New predictions go to fresh filenames per experiment.
- Reporting `B_test score` more than once per merge attempt counts as leakage; only `arbor-critic` should invoke it at merge time.

## Edit surface

- Allowed to modify: `.agent/config/router_rules.json`, or add new files under `.agent/datasets/arbor-router-training/` (e.g. a `predict_v2.py`).
- Protected: `B_test.jsonl`, `B_dev.jsonl`, `eval.py`, `ARBOR_CONTRACT.md`, `research_config.yaml`, `baseline.json`, `baseline_*.jsonl`. Any patch touching these must be flagged to `arbor-critic`.

## Hard constraints

- No changes to `eval.py` that would silently rescale the metric.
- No importing labels from `B_test.jsonl` at prediction time (including via embedding-similarity to test rows).
- All experiments must run offline: no external LLM calls in the predictor, since routing decisions must be cheap.
- All new Python must run on the stdlib + whatever is already imported in the repo. No new heavyweight ML deps (torch/sklearn) without RFC.

## Budget

- Suggested `coordinator.max_cycles`: 6.
- Wall-clock: soft cap 30 min per cycle (each cycle: propose → executor edit → re-run baseline → decide).
- Interaction mode: `review` — the coordinator surfaces each promote/prune to the human validator (workflow node "Human Validate") before merging to trunk.
