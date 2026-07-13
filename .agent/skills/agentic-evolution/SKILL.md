---
name: agentic-evolution
description: Protocols for autonomous agent kit improvement and self-specialization.
version: 1.0.0
---

# Agentic Evolution

This skill provides the logic and scripts for the autonomous evolution of the Agentic OS.

## Principles

1. **Self-Diagnosis**: Analyzing `LESSONS_LEARNED.md` and `telemetry/` to find bottlenecks.
2. **Specialization**: Creating new agents for niche domains to reduce "role fatigue" of generic agents.
3. **Consensus Duels**: Running parallel models to verify logic.

## Workflows

- **Breeding Cycle**: Pattern detection → Agent Profile Generation → Skill Scaffolding.
- **Intelligence Regression**: Running "Golden Task" benchmarks.

## Scripts

- `.agent/scripts/orchestration/agent_breeder.py`
- `.agent/scripts/orchestration/arena_engine.py`
- `.agent/scripts/qa/intelligence_benchmark.py`
- `.agent/scripts/lib/llm_client.py`

## When to Use

- **Triggering the breeding cycle** when `LESSONS_LEARNED.md` shows repeated
  failure patterns for a single agent role.
- **Running intelligence benchmarks** to measure quality drift after
  agent or skill changes.
- **Creating a new specialist agent** when an existing role accumulates
  too many responsibilities (signaled by telemetry: `applied_count`
  on lessons > 30 over a sprint).
- **Reviewing consensus duels** when two agents disagree on a plan and
  need a third opinion.

Avoid using this skill for:
- One-off agent improvements (use `@agent-development` instead).
- Performance tuning of a single LLM call (use `@performance-optimizer`).

## Anti-Patterns

- **Don't breed agents for every niche** — each new agent is a
  coordination cost. Breed only when existing roles have a
  measurable bottleneck.
- **Don't skip the regression suite** — every new agent must pass
  `intelligence_benchmark.py` before being added to the manifest.
- **Don't trust self-reported quality** — agents can lie about their
  own performance. Use the `Golden Task` benchmark as ground truth.
- **Don't breed without `LESSONS_LEARNED.md` evidence** — if there
  are no lessons, there's no signal. Wait for failure data to
  accumulate.

## Changelog

- **1.0.0** (2026-05-22): Initial version
