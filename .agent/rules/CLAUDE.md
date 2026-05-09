# CLAUDE.md — Prompt Library (Antigravity Kit Hub)

> This is the **source repository** for Antigravity Kit. Agents, skills, workflows, and templates
> are maintained here and distributed to target repositories via GitHub Actions.
> It does NOT contain application code.

## 📥 REQUEST CLASSIFIER

**Before ANY action, classify the request:**

| Request Type     | Trigger Keywords                           | Active Tiers                   | Result                      |
| ---------------- | ------------------------------------------ | ------------------------------ | --------------------------- |
| **QUESTION**     | "what is", "how does", "explain"           | TIER 0 only                    | Text Response               |
| **SURVEY/INTEL** | "analyze", "list files", "overview"        | TIER 0 + Explorer              | Session Intel (No File)     |
| **SIMPLE CODE**  | "fix", "add", "change" (single file)       | TIER 0 + TIER 1 (lite)         | Inline Edit                 |
| **COMPLEX CODE** | "build", "create", "implement", "refactor" | TIER 0 + TIER 1 (full) + Agent | **{task-slug}.md Required** |
| **DESIGN/UI**    | "design", "UI", "page", "dashboard"        | TIER 0 + TIER 1 + Agent        | **{task-slug}.md Required** |
| **SLASH CMD**    | /create, /orchestrate, /debug              | Command-specific flow          | Variable                    |

---

## 🤖 INTELLIGENT AGENT ROUTING (Adaptive Routing)

**ALWAYS ACTIVE: Before responding to ANY request, analyze and select the best agent(s).**

| Level | Name | Description | Active Units |
| :--- | :--- | :--- | :--- |
| **L1** | **Sprint** | Direct response from a single domain expert. | 1 Specialist Agent |
| **L2** | **Pro** | Implementation with mandatory self-reflection/critique pass. | 1 Specialist + Self-Critic |
| **L3** | **Council** | Synthetic consensus of multiple perspectives before action. | Architect + Specialist + SRE |
| **L4** | **Control** | Mission-critical audit with security testing. | Red Team + Security + QA |

---

## 📎 Paperclip Heartbeat Protocol (MANDATORY)

**Every session with ANY agent MUST follow the Paperclip Heartbeat cycle:**

1. Awareness: Sync with current task and read `.agent/bus/` for context.
2. Lenses: Apply Domain Lenses based on role category (Management, Engineering, QA, Infra).
3. Action: Do not stop at planning; perform actionable work in the same heartbeat.
4. Reporting: Every session MUST end with a **Progress Report** (Status, Blockers, Next Action).
5. Durable State: Update task metadata and create child issues for delegated work.

---

## 🛑 SOCRATIC GATE (TIER 0)

**MANDATORY: Every user request must pass through the Socratic Gate before ANY implementation.**

1. Never Assume: If even 1% is unclear, ASK.
2. Handle Spec-heavy Requests: Ask about **Trade-offs** or **Edge Cases** before starting.
3. Wait: Do NOT write code until the user clears the Gate.

---

## 🏗️ Agent & Skill System

Agents live in two locations:

| Location          | Platform             | Usage                                 |
| ----------------- | -------------------- | ------------------------------------- |
| `.agent/agents/`  | Antigravity (Gemini) | Source of truth — edit here           |
| `.claude/agents/` | Claude Code          | Auto-generated — do not edit directly |

Skills live in `.agent/skills/` and are embedded into `.claude/agents/` by `sync_claude_agents.py`.

### Specialist Agents (Adopt profile when active)

| Category     | Path                                  | Agents                                              |
| ------------ | ------------------------------------- | --------------------------------------------------- |
| **Core**     | `.agent/agents/core/`                 | orchestrator, project-planner, reviewer, maintainer |
| **Domain**   | `.agent/agents/domain/`               | backend-specialist, frontend-specialist, mobile-developer, ai-engineer |
| **QA**       | `.agent/agents/qa/`                   | debugger, test-engineer, performance-optimizer      |
| **Security** | `.agent/agents/specialists/security/` | security-auditor, red-team, penetration-tester      |

---

## 🛠️ Workflows (Slash Commands)

Workflows in `.agent/workflows/` define procedures. Claude MUST read them before execution.

| Command              | Path                   | Purpose                           |
| -------------------- | ---------------------- | --------------------------------- |
| `/discovery`         | `discovery.md`         | BMAD Phase 1 — Socratic brief     |
| `/prd`               | `prd.md`               | BMAD Phase 2 — PRD from brief     |
| `/architecture-bmad` | `architecture-bmad.md` | BMAD Phase 3 — Architecture + ADRs|
| `/stories`           | `stories.md`           | BMAD Phase 4 — Story card batch   |
| `/sprint`            | `sprint.md`            | BMAD Phase 5 — Sprint board       |
| `/orchestrate`       | `orchestrate.md`       | Multi-agent coordination          |

---

## 🧹 Clean Code (Global Mandatory)

- **Code**: Concise, direct, no over-engineering. Self-documenting.
- **Testing**: Mandatory. Pyramid (Unit > Int > E2E) + AAA Pattern.
- **Performance**: Measure first. Adhere to 2025 standards.
- **Rules**: Follow `@[skills/clean-code]` rules.

---

## 📜 Technical Standards & Verification

**Before completing any task, run appropriate verification scripts:**

- `python3 .agent/scripts/status_report.py` - Check workspace health.
- `python3 .agent/scripts/checklist.py .` - Priority-based validation.
- `python3 .agent/scripts/compile_rules.py` - After editing Gemini rules.
- `python .agent/scripts/sync_claude_agents.py` - **MANDATORY** after editing agents or skills.

## Architecture Reference

@.agent/ARCHITECTURE.md
@.agent/KNOWLEDGE.md

## Commit Convention

Follow Conventional Commits: `feat(agent):`, `chore(agent):`, `docs(agent):`, `fix(agent):`.
