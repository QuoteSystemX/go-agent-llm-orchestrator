---
name: neural-prd-engineering
description: AI-assisted Product Requirements Document (PRD) generation. Using LLMs to bridge the gap between vague ideas and atomic engineering stories.
allowed-tools: Read, Write, Edit, Glob, Grep
version: 1.0.0
---

# Neural PRD Engineering

> Transforming intuition into executable specs using Agentic reasoning.

---

## 1. The High-Fidelity PRD Stack

A 2026 PRD isn't just text; it's a prompt for the engineering agents.

| Section | AI Action | Output Format |
|---------|-----------|---------------|
| **Intent Map** | Extract core "Why" | Mermaid Flowchart |
| **User Journey** | Simulate step-by-step | Gherkin Scenarios |
| **Edge Case Audit** | Adversarial "Red Team" check | Risk Matrix |
| **Data Schema** | Infer entities/relations | DBML / SQL |
| **API Specs** | Draft endpoints | OpenAPI (YAML) |

---

## 2. Extraction Protocol

When the user gives a vague requirement:

1. **Expansion**: Run `requirement_expander.py` to find missing context.
2. **Simulation**: Ask the LLM to "act as a user" and try to break the flow.
3. **Decomposition**: Break the feature into "Atomic Stories" (one feature, one test).

---

## 3. Gherkin for AOS Agents

AOS Agents (like `test-engineer`) eat Gherkin for breakfast.

```gherkin
Feature: User Authentication

  Scenario: Successful login with valid credentials
    Given the user is on the login page
    When they enter "artur@gemini.com" and "correct-password"
    And click "Submit"
    Then they should be redirected to "/dashboard"
    And see a "Welcome" notification
```

---

## 4. The "No-Gap" Rule

Every PRD must answer:
- **Success Metric**: How do we know it works? (e.g., `< 200ms latency`)
- **Failure Mode**: What if the API is down? (e.g., `show cached data`)
- **Security Scope**: Who can access this? (e.g., `role: admin`)

---

## 5. Automation Tools

| Tool | Purpose |
| :--- | :--- |
| `prd_validator.py` | Checks if a PRD has all 5 mandatory sections. |
| `story_decomposer.py` | Turns a PRD section into atomic `tasks/*.md` cards. |

---

> **Principle:** If a requirement is not specific enough for an LLM to code it, it's not specific enough for a PRD.

## Changelog

- **1.0.0** (2026-05-13): Initial version

## When to Use

- **Turning a vague idea into a structured PRD** — use the
  `requirement_expander.py` script to find missing context.
- **Decomposing a feature into atomic stories** — run
  `story_decomposer.py` on a PRD section to generate `tasks/*.md`
  cards that the squad orchestrator can pick up.
- **Validating an existing PRD** — run `prd_validator.py` to check
  it has all 5 mandatory sections (Intent Map, User Journey,
  Edge Cases, Data Schema, API Specs).
- **Adversarial review** — use the "Red Team" edge case audit to
  find failure modes before implementation.
- **Cross-team alignment** — share the PRD as a Mermaid flowchart
  + Gherkin scenarios for unambiguous discussion.

Avoid using this skill for:
- Bug fixes (use `@debugger`).
- Documentation (use `@documentation-writer`).
- Architecture decisions (use `@architect`).
- Simple tasks that don't need a full PRD.

## Anti-Patterns

- **Don't write PRDs that are too vague to code** — if an LLM can't
  code from the PRD, a human can't either. Be specific.
- **Don't skip the Edge Case Audit** — it catches the 20% of cases
  that consume 80% of engineering time.
- **Don't use "happy path only" Gherkin** — always include at least
  2-3 negative cases per scenario.
- **Don't decompose stories too granularly** — atomic means "one
  feature, one test", not "one line, one test". A 200-line story
  is fine; 5-line stories create coordination overhead.
- **Don't skip the Schema section** — if the feature touches data,
  include the schema. Mismatched schemas are the #1 cause of
  integration bugs.
- **Don't write PRDs in isolation** — share with the squad
  orchestrator and let agents flag ambiguities early.
