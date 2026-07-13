---
name: architecture
description: Architectural decision-making framework. Requirements analysis, trade-off evaluation, ADR documentation. Use when making architecture decisions or analyzing system design.
allowed-tools: Read, Glob, Grep
version: 1.0.0
---

# 🏛 System Architecture & Design

Expert guidelines for designing scalable, maintainable, and resilient software architectures.

## 🏗 Core Methodology: ADR-First

Every significant architectural change MUST be documented in an **Architecture Decision Record (ADR)**. This ensures transparency, history, and rationale for future maintainers.

### Key Sections of an ADR:
1. **Context**: Why are we doing this?
2. **Decision Drivers**: What metrics or goals are we optimizing for?
3. **Considered Options**: What else did we look at?
4. **Outcome**: What did we choose and why?
5. **Consequences**: What are the trade-offs (positive and negative)?

## 🎯 Decision Drivers & Lenses

Apply these lenses to every architectural proposal:
- **Scalability**: Can it handle 10x load?
- **Maintainability**: Can a new developer understand this in 30 minutes?
- **Observability**: How will we know when it breaks?
- **Security**: Is it secure by default?
- **Cost**: Is it cloud-native and cost-efficient?

## 🚀 Tools & Verification

### 1. ADR Scaffolder
Create a new architectural decision record using the internal tool:

```bash
python3 .agent/skills/architecture/scripts/generate_adr.py "Decision Title"
```

### 2. Architecture Linter
Refer to `examples/adr-001-template.md` for a "Golden Path" of ADR documentation.

## 📈 Architecture Checklist
- [ ] Is there an ADR for this change?
- [ ] Are trade-offs explicitly documented?
- [ ] Is the dependency flow unidirectional (Inner → Outer)?
- [ ] Is the data model decoupled from the UI?
- [ ] Are failure modes identified and mitigated?

---
> **Note**: This skill ensures that Paperclip's evolution is deliberate, documented, and durable.


## When to Use

- **Designing a new system** — start with the 4-quadrant view
  (C4 model: Context, Container, Component, Code).
- **Documenting an existing system** — capture current state
  before refactoring.
- **Communicating architecture to non-technical stakeholders** —
  use the C4 diagrams (auto-rendered from Mermaid).
- **Comparing architecture options** — write ADR-001, ADR-002, etc.
  with diagrams, tradeoffs, and decision rationale.
- **Onboarding new team members** — `ARCHITECTURE.md` is the entry
  point for understanding "how this thing works".

Avoid using this skill for:
- One-off code changes (use `@backend-specialist` or similar).
- Bug fixes (use `@debugger`).
- Feature planning (use `@product-manager`).

## Anti-Patterns

- **Don't create diagrams that lie** — auto-generated C4 from
  code is more trustworthy than hand-drawn diagrams that go stale.
- **Don't document "what" without "why"** — every box on the
  diagram needs context (why does it exist, who uses it).
- **Don't use 10+ levels of nesting** — keep diagrams to 2-3 levels
  (System → Container → Component). Deeper = harder to read.
- **Don't duplicate info between code and docs** — if the code says
  X, the docs shouldn't say Y. Either update the code or remove
  the doc.
- **Don't use "Architecture" as a single document** — split into
  per-component docs (auth.md, db.md, api.md) with a top-level
  index.
- **Don't skip the "Rationale" section in ADRs** — "we chose X
  because Y" is the most-valuable part. Future readers will thank you.

## Changelog

- **1.0.0** (2026-05-13): Initial version
