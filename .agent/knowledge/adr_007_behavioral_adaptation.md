# ADR-007: Behavioral Adaptation & Arena Protocol

## Status

Accepted ✅

## Context

As part of the Orchestration v3.1 upgrade, the system needs to:

1. Adapt to the user's stylistic DNA (Conciseness, Tone, Philosophy).
2. Resolve conflicts when multiple agents are suitable for a subtask using a competitive "Arena" protocol.

## Decision

1. **PERSONA.md**: A new source of truth for User DNA located in `.agent/rules/PERSONA.md`.
2. **personality_adapter.py**: A service that parses `PERSONA.md` and broadcasts preferences to the Context Bus (`.agent/bus/personality_profile.json`).
3. **Arena Protocol**:
   - Triggered by `agent_auctioneer.py` when >1 candidates exist.
   - Uses 2 rounds of reasoning (Strategy & Critique, then Rebuttal).
   - Judged by `project-planner` or `arbitrator` based on alignment with User DNA.

## Consequences

- Agents now produce output that feels more personalized to the user.
- Conflict resolution is transparent and documented in the session state.
- Minor overhead for session initialization (parsing persona).
