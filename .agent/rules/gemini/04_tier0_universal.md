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

- **Semantic Awareness**: Before modifying any code in a supported language (Go, Markdown), the agent MUST verify the target symbol's semantic state (definitions, references) using the LSP Gateway tools (`semantic_definition`, `semantic_hover`).
- **Code**: Concise, direct, no over-engineering. Self-documenting.
- **Testing**: Mandatory. Pyramid (Unit > Int > E2E) + AAA Pattern.
- **Performance**: Measure first. Adhere to 2025 standards (Core Web Vitals).
- **Infra/Safety**: 5-Phase Deployment. Verify secrets security.

### 🏥 SYSTEM HEALTH FIRST (Global Protocol)

**Before performing ANY task that modifies code or project state:**

1.  **Check Health**: Run `python3 .agent/scripts/health/status_report.py`. If score < 80, investigate why.
2.  **Check Semantic Gateway**: Ensure `gopls` and `marksman` are active via `semantic_hover` probe.
3.  **Check Conflicts**: Run `python3 .agent/scripts/context/conflict_resolver.py`. DO NOT proceed if conflicts exist.
3.  **Check Budget**: Run `python3 .agent/scripts/health/guardrail_monitor.py`. DO NOT exceed token/cost limits.
4.  **Check Experience**: Run `python3 .agent/scripts/knowledge/experience_distiller.py`. Learn from past failures.
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
### 💰 Token Optimization (Global Mandatory)

**ALL agents MUST apply these optimizations at ALL times — no exceptions.**

#### 🛡️ RTK — Prefix every shell command
```bash
rtk git status       # instead of: git status
rtk ls src/          # instead of: ls src/
rtk grep "x" .       # instead of: grep "x" .
```
RTK filters command output before it reaches LLM context, saving 60-90% tokens.

### 🔀 Parallel Task Execution & Concurrency
When executing tasks in parallel (e.g., dev work by `go-specialist` and testing by `test-engineer` via the squad orchestrator):
1. **File Isolation**: Agents must modify strictly separate files (e.g., business logic in `app.go`, tests in `app_test.go`) to prevent write conflicts and git merge conflicts.
2. **Broker Queueing**: Parallel requests are governed by `mcp-llm-broker` semaphores. Do not implement custom concurrency in python scripts; let the broker handle LLM load balancing.

### 🚫 NO COMMITS WITHOUT EXPLICIT USER PERMISSION (MANDATORY)

**Creating a git commit — or any git history-mutating operation (commit, amend, rebase, push, merge) — is FORBIDDEN without the user's explicit, per-operation approval.**

1. **Always ask first**: Before running `git commit` (or any mutating git command), STOP and ask the user for explicit permission. Do not assume consent from context (e.g., "the task is done", "the previous commit was approved", "commits were allowed earlier in the session").
2. **One permission per operation**: User approval of one commit does NOT authorize subsequent commits. Ask again for each new commit.
3. **Explicit permission defined**: The user must clearly confirm (e.g., "да, закоммить", "commit it", "сделай коммит"). Silence, prior patterns, or a generic "continue" do NOT count as permission.
4. **Staging is allowed**: `git add` (staging) is permitted without approval — it is non-destructive and lets the user review what would be committed. But do NOT commit staged changes without permission.
5. **Branching/rebasing/pushing**: Creating branches, rebasing, force-pushing, or pushing to remotes are destructive/mutating operations — each requires explicit user permission.
6. **When in doubt**: If the user has not clearly authorized a commit for the current change, leave changes uncommitted (working tree + staged files) and report the state, offering to commit on their word.

