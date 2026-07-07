---
name: architecture-governance
description: "Enforcing architectural standards, maintaining codebase health, preventing directory drift, and documenting decisions using Architecture Decision Records (ADRs)."
version: 1.0.0
---

# Architecture Governance Skill (Master Level)

This skill defines the procedures and mandatory rules for enforcing architectural standards, maintaining codebase health, preventing directory drift, and documenting decisions using Architecture Decision Records (ADRs).

---

## 🎯 Primary Goal
Maintain a premium, high-integrity directory and package structure, validate dependencies globally, and prevent unapproved patterns.

---

## 🏛 Directory Governance & Naming Conventions

All modules and agent structures must strictly follow these rules:

| Entity | Pattern | Location | Examples |
| :--- | :--- | :--- | :--- |
| **Core Agents** | `core/*.md` | `.agent/agents/core/` | `orchestrator.md`, `maintainer.md` |
| **Specialist Agents**| `[domain]/[name].md` | `.agent/agents/specialists/` | `go/crypto-go-architect.md` |
| **Domain Agents** | `domain/*.md` | `.agent/agents/domain/` | `mobile-developer.md` |
| **Skill Modules** | Directory containing `SKILL.md` | `.agent/skills/` | `clean-code/`, `go-patterns/` |

> [!WARNING]
> Ad-hoc skills or agent files written directly under `.agent/` or `/tmp` are strictly prohibited. The Sentinel Gate will block any PR with unapproved file topologies.

---

## 🛡️ Active Tools & Execution Guidelines

### 1. Drift Validation (Wiki-First Enforcement)
Before modifying any core packages, agents must check if the code matches the documented mental models.

```bash
# Detect gaps between code and documentation
python3 .agent/scripts/health/drift_detector.py --module <module_name>
```

#### Example Output Analysis:
```text
📊 DRIFT DETECTOR:
  - Component: pkg/auth/session.go
  - Associated Doc: wiki/mental-models/auth.md
  ❌ CRITICAL DRIFT: wiki claims token invalidation is active; code lacks session revocation logic.
```
*Action:* If a critical drift is detected, you **MUST** create a blocking task to align either the wiki or the code before checking in changes.

### 2. Decision Capture via ADRs
Every architectural decision (e.g., swapping a library, adding a db model, changing API contracts) must be logged as an ADR.

```bash
# Generate a new ADR scaffolding
python3 .agent/scripts/knowledge/adr_generator.py "Migrate to Neon Postgres"
```

#### Approved ADR Template:
```markdown
# ADR-0012: Migrate to Neon Postgres

## Context
Our current SQLite setup is hitting connection limits during parallel agent runs. We need a serverless Postgres option to scale.

## Decision
We will migrate our database layer to Neon Serverless Postgres using Drizzle ORM.

## Consequences
- **Pros**: Dynamic scaling, connection pooling out-of-the-box, branching support.
- **Cons**: Introduce network latency (mitigated via local caching).

## Status
Approved (Supersedes ADR-0004)
```

---

## 🏆 Checklist for Enforcement
- [ ] **Dependency Cycle Check**: Run `visualize_deps.py` to ensure no recursive imports.
- [ ] **Archived References**: When removing a skill or replacing a module, move the old directories to `.agent/skills/archive/` instead of deleting them outright to preserve learning history.
- [ ] **LSP Gateway Probe**: Always probe semantic references using `semantic_hover` before renaming shared variables or structural types.
