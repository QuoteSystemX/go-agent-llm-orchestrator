---
trigger: always_on
---

# GEMINI.md - Unified Agent Kit

> This file defines how the AI behaves in this workspace.

---

## CRITICAL: AGENT & SKILL PROTOCOL (START HERE)

> **MANDATORY:** You MUST read the appropriate agent file and its skills BEFORE performing any implementation. This is the highest priority rule.

### 1. Modular Skill Loading Protocol

Agent activated → Check frontmatter "skills:" → Read SKILL.md (INDEX) → Read specific sections.

- **Selective Reading:** DO NOT read ALL files in a skill folder. Read `SKILL.md` first, then only read sections matching the user's request.
- **Rule Priority:** P0 (GEMINI.md) > P1 (Agent .md) > P2 (SKILL.md). All rules are binding.

### 2. Enforcement Protocol

1. **When agent is activated:**
    - ✅ Activate: Read Rules → Check Frontmatter → Load SKILL.md → Apply All.
2. **When rules are modified:**
    - ✅ **MANDATORY:** After editing files in `.agent/rules/gemini/`, you MUST run `python3 .agent/scripts/dev/compile_rules.py` (or `/sync-rules`) to update the monolithic rule file.
3. **Forbidden:** Never skip reading agent rules or skill instructions. "Read → Understand → Apply" is mandatory.
