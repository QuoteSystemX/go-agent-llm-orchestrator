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

## Changelog

- **1.0.0** (2026-05-13): Initial version
