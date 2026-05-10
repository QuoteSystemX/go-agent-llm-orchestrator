---
trigger: always_on
---

## TIER 0: UNIVERSAL RULES (Always Active)

### 🌐 Language Handling

When user's prompt is NOT in English:

1. **Internally translate** for better comprehension
2. **Respond in user's language** - match their communication
3. **Code comments/variables** remain in English

### 🧹 Clean Code (Global Mandatory)

**ALL code MUST follow `@[skills/clean-code]` rules. No exceptions.**

- **Code**: Concise, direct, no over-engineering. Self-documenting.
- **Testing**: Mandatory. Pyramid (Unit > Int > E2E) + AAA Pattern.
- **Performance**: Measure first. Adhere to 2025 standards (Core Web Vitals).
- **Infra/Safety**: 5-Phase Deployment. Verify secrets security.

### 🏥 SYSTEM HEALTH FIRST (Global Protocol)

**Before performing ANY task that modifies code or project state:**

1.  **Check Health**: Run `python3 .agent/scripts/status_report.py`. If score < 80, investigate why.
2.  **Check Conflicts**: Run `python3 .agent/scripts/conflict_resolver.py`. DO NOT proceed if conflicts exist.
3.  **Check Budget**: Run `python3 .agent/scripts/guardrail_monitor.py`. DO NOT exceed token/cost limits.
4.  **Check Experience**: Run `python3 .agent/scripts/experience_distiller.py`. Learn from past failures.
5.  **Browser Access**: If web access is needed, MUST use `bin/browser-bridge`. Never attempt raw browser calls without the resilience bridge.

> 🔴 **MANDATORY**: A task is only complete if `checklist.py . --fix` has been run and returns success.

### �� File Dependency Awareness

**Before modifying ANY file:**

1. Check `CODEBASE.md` → File Dependencies
2. Identify dependent files
3. Update ALL affected files together

### 🗺️ System Map Read

> 🔴 **MANDATORY:** Read `ARCHITECTURE.md` at session start to understand Agents, Skills, and Scripts.

**Path Awareness:**

- Agents: `.agent/` (Project)
- Skills: `.agent/skills/` (Project)
- Runtime Scripts: `.agent/skills/<skill>/scripts/`

### 🧠 Read → Understand → Apply

```
❌ WRONG: Read agent file → Start coding
✅ CORRECT: Read → Understand WHY → Apply PRINCIPLES → Code
```

**Before coding, answer:**

1. What is the GOAL of this agent/skill?
2. What PRINCIPLES must I apply?
3. How does this DIFFER from generic output?
