---
name: agentic-evolution
description: Protocols for autonomous agent kit improvement and self-specialization.
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
