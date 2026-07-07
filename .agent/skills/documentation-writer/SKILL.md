---
name: documentation-writer
description: "Writing architecture summaries, onboarding guides, and compliance reports with Prose-First standards."
version: 1.0.0
---

# Documentation Writer Skill (Master Level)

This skill defines the rules, markup conventions, and prose standards for writing premium architecture summaries, onboarding guides, and compliance reports.

---

## 🎯 Primary Goal
Enforce Karpathy-style Prose-First documentation: write the specifications and mental models *before* implementing feature code. Eliminate structural drift automatically.

---

## ✍️ Prose-First Documentation Lifecycle

When tasked with writing system guides or ethics compliance reviews, apply this protocol:

### 1. The Intuition-First Principle
Do **NOT** write lists of API handlers or classes as documentation. Always lead with a **visceral analogy** that helps a human engineer build a strong mental model instantly.

#### Bad Example (Purely technical):
```markdown
## SessionManager
Contains a dictionary of sessions mapping session strings to User structs. Access is synchronized via a mutex.
```

#### Good Example (Intuition-First):
```markdown
## Session Manager (Intuition)
Think of the Session Manager as a secure coat-check in a theater. 

The client exchanges their bulky credentials for a lightweight, temporary ticket (the Session Token). Whenever they want to access private rooms, they show this ticket. The manager matches the ticket number to the checked coat (the User Struct) on the rack, retrieving user permissions in under 2ms.
```

---

## 📋 Approved Compliance & Ethical Audit Template

For AI-assisted software systems, the `ethics-auditor` agent must compile an ethical compliance log.

```markdown
# AI Safety & Bias Compliance Audit

## 1. System Overview & Trust Boundaries
- **Component**: Neural prompt classification engine.
- **Trust Boundary**: Prompt input boundaries are strictly sanitized before passing to LLM to prevent prompt injection.

## 2. Risk Modeling & Bias Mitigation
- **Bias Profile**: High potential for language bias.
- **Mitigation Strategy**: The engine normalizes syntax across English, Russian, and Spanish translations before analyzing semantic properties to maintain classification consistency.

## 3. Data Integrity & Privacy
- **PII Protection**: Dynamic masking of emails, phone numbers, and API keys is enforced at the context gateway.
- **Logging Policy**: Raw prompts containing PII are never persisted in execution traces.
```

---

## 🧹 Automatically Healing Drift
Run `doc_healer.py` immediately after editing structural directories or packages to update the system map.

```bash
# Analyze repository changes and heal doc drift in ARCHITECTURE.md
python3 .agent/scripts/dev/doc_healer.py --heal
```
