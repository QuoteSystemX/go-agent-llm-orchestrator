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
