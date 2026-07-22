# Arbor Router-Training Dataset

Training + held-out dataset the Arbor Squad's autonomous research loop consumes during workflow **Arbor Squad Training** (run `#708be80f`, node `Prepare Dataset`). Downstream node: `Discuss / Reason` — the Arbor Squad reasons over this dataset via the Idea Tree / ReAct loop; then `Human Validate` before `Push Result`.

## What the squad is being trained to do

Predict, from a natural-language engineering task description, the correct **model-complexity tier** (`L1`..`L4`) so the LLM router picks the cheapest capable model. Today the router is the keyword-weighted rules in `.agent/config/router_rules.json`; the squad may keep, tune, replace, or augment it — as long as the resulting predictor is a pure function `task_text → tier` that runs offline.

## Files

| File                       | Purpose                                                      |
| -------------------------- | ------------------------------------------------------------ |
| `B_dev.jsonl`              | 40 labeled examples. Iterate on these.                       |
| `B_test.jsonl`             | 20 held-out examples. Do not tune on them.                   |
| `eval.py`                  | Scores a predictions JSONL. Prints `score: <float>` + JSON.  |
| `predict_baseline.py`      | Runs the current rule-based router → predictions JSONL.      |
| `baseline_dev.jsonl`       | Baseline predictor output on B_dev (frozen).                 |
| `baseline_test.jsonl`      | Baseline predictor output on B_test (frozen).                |
| `baseline.json`            | Recorded baseline metrics + notes on failure modes.          |
| `ARBOR_CONTRACT.md`        | One-screen research contract for `arbor-coordinator` INIT.   |
| `research_config.yaml`     | Machine-readable contract; auto-detected by `arbor` tooling. |

## Schema

Each example (both splits):

```json
{"id": "dev-001", "lang": "en|ru", "task": "<task description>", "label": "L1|L2|L3|L4"}
```

Each prediction:

```json
{"id": "dev-001", "predicted": "L1|L2|L3|L4"}
```

## Label semantics

Tiers follow `router_rules.json / agent_tiers` and match how the fleet is priced today (`pricing_per_1k_tokens`):

- **L1** — trivial: typos, formatting, renaming, doc edits. Local / haiku-tier is enough.
- **L2** — standard engineering: feature, small refactor, unit tests, single-service bug. Balanced cloud model.
- **L3** — deep work: debugging concurrency, security audits, subsystem refactor, architecture decisions.
- **L4** — critical/system-wide: zero-day audit, cross-cluster migration plan, monolith split.

## Split composition

|         | L1 | L2 | L3 | L4 | total |
| ------- | -- | -- | -- | -- | ----- |
| B_dev   | 10 | 14 | 10 |  6 |  40   |
| B_test  |  5 |  6 |  5 |  4 |  20   |

Every tier is present in both splits, and both English and Russian phrasings appear (matching the router's bilingual keyword weights). Examples are drawn from realistic tasks against QuoteSystemX repos: `RecipientOFQuotes`, the emulator, `model-ML`, `Infra`.

## Metric

```
per_example = max(0, 1 − 0.15·overshoot − 0.35·undershoot)
overshoot   = max(0, tier(pred) − tier(true))   # cost waste
undershoot  = max(0, tier(true) − tier(pred))   # quality risk
score       = mean(per_example)                  # maximize
```

Undershoots are penalized more than overshoots because misrouting L4 work to L1 causes a real failure downstream (agent gets in over its head), whereas overshoot is "only" wasted money.

Accuracy is reported alongside `score` as a secondary observable. `score` is the one the squad optimizes; watching accuracy separately keeps them honest about whether they're actually getting rows right vs. just hugging the middle tiers.

## Baseline (frozen)

Rule-based router (`.agent/config/router_rules.json` as of 2026-07-22):

- **B_dev**: score 0.8088, accuracy 0.425
- **B_test**: score 0.795, accuracy 0.55

Failure modes visible in the confusion matrix (`baseline.json`):
1. L1 tasks overpredicted as L2 — the base score of 5 already lands in L2's band before any keywords fire.
2. L3/L4 tasks routed too cheap — the "critical audit"/"migration plan" phrase weights are strong, but plainer L3 tasks slip through.

These are the two levers the squad should pull first.

## How to reproduce the baseline

```bash
cd .agent/datasets/arbor-router-training
python3 predict_baseline.py --split B_dev  --out baseline_dev.jsonl
python3 predict_baseline.py --split B_test --out baseline_test.jsonl
python3 eval.py --split B_dev  --predictions baseline_dev.jsonl
python3 eval.py --split B_test --predictions baseline_test.jsonl
```

## Handoff

The next workflow node (`Discuss / Reason`, executor: Arbor Squad) starts by reading `ARBOR_CONTRACT.md` and `research_config.yaml`. Everything the coordinator's INIT phase needs (metric command, baseline, splits, protected paths, budget, interaction mode) is in there — the squad does not need to re-derive it.
