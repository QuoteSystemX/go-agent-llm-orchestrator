# Antigravity Kit Architecture

> Comprehensive AI Agent Capability Expansion Toolkit

---

## 📋 Overview

Antigravity Kit is a modular system consisting of:

- **24 Specialist Agents** - Role-based AI personas
- **41 Skills** - Domain-specific knowledge modules
- **18 Workflows** - Slash command procedures

---

## 🏗️ Directory Structure

```plaintext
.agent/
├── ARCHITECTURE.md          # This file
├── KNOWLEDGE.md             # Global Rules, Context, and Orchestration Standards
├── agents/                  # Specialist Agents profiles (.md)
├── skills/                  # Skills (Domain-specific knowledge modules)
├── workflows/               # Slash Commands for Antigravity (+ Local triggers)
├── rules/                   # Global Rules (GEMINI.md)
└── scripts/                 # Master Validation Scripts

# Prompt Library Hub Features (Repository Root)
├── prompt/patterns/         # Execution Methodologies (featureforge, bugcatcher, reviewer)
├── tasks/                   # Active Agent Task Queue
└── .github/distribution.yml # CRON Task Distribution Map
```

---

## 🤖 Agents (26)

Specialist AI personas for different domains.

| Agent                    | Focus                      | Skills Used                                                       |
| ------------------------ | -------------------------- | ----------------------------------------------------------------- |
| `orchestrator`           | Multi-agent coordination   | parallel-agents, behavioral-modes, intelligent-routing            |
| `analyst`                | BMAD lifecycle driver      | bmad-lifecycle, plan-writing, brainstorming, architecture         |
| `project-planner`        | Discovery, task planning   | brainstorming, plan-writing, architecture                         |
| `frontend-specialist`    | Web UI/UX                  | frontend-design, nextjs-react-expert, tailwind-patterns, i18n-localization |
| `backend-specialist`     | API, business logic        | api-patterns, nodejs-best-practices, database-design              |
| `database-architect`     | Schema, SQL                | database-design                                                   |
| `mobile-developer`       | iOS, Android, RN           | mobile-design, i18n-localization                                  |
| `game-developer`         | Game logic, mechanics      | game-development                                                  |
| `crypto-go-specialist`   | Go, Microservices, Perf    | go-patterns, api-patterns, architecture                           |
| `devops-engineer`        | CI/CD, Docker              | deployment-procedures, server-management                          |
| `security-auditor`       | Security compliance        | vulnerability-scanner, red-team-tactics                           |
| `penetration-tester`     | Offensive security         | red-team-tactics                                                  |
| `test-engineer`          | Testing strategies         | testing-patterns, tdd-workflow, webapp-testing                    |
| `debugger`               | Root cause analysis        | systematic-debugging                                              |
| `performance-optimizer`  | Speed, Web Vitals          | performance-profiling                                             |
| `seo-specialist`         | Ranking, visibility        | seo-fundamentals, geo-fundamentals                                |
| `documentation-writer`   | Manuals, docs              | documentation-templates, i18n-localization                        |
| `product-manager`        | Requirements, user stories | plan-writing, brainstorming                                       |
| `product-owner`          | Strategy, backlog, MVP     | plan-writing, brainstorming                                       |
| `qa-automation-engineer` | E2E testing, CI pipelines  | webapp-testing, testing-patterns                                  |
| `code-archaeologist`     | Legacy code, refactoring   | clean-code, code-review-checklist                                 |
| `rest-api-designer`      | REST / OpenAPI design      | api-patterns, typescript-expert, documentation-templates          |
| `grpc-architect`         | gRPC / Protobuf design     | go-patterns, api-patterns, architecture                           |
| `explorer-agent`         | Codebase analysis          | -                                                                 |
| `reviewer`               | Automated code auditing    | code-review-checklist, vulnerability-scanner, systematic-debugging |

---

## 🧩 Skills (41)

Modular knowledge domains that agents can load on-demand. based on task context.

### Frontend & UI

| Skill                   | Description                                                           |
| ----------------------- | --------------------------------------------------------------------- |
| `nextjs-react-expert`   | React & Next.js performance optimization (Vercel - 57 rules)          |
| `web-design-guidelines` | Web UI audit - 100+ rules for accessibility, UX, performance (Vercel) |
| `tailwind-patterns`     | Tailwind CSS v4 utilities                                             |
| `frontend-design`       | UI/UX patterns, design systems                                        |
| `ui-ux-pro-max`         | 50 styles, 21 palettes, 50 fonts                                      |

### Backend & API

| Skill                   | Description                                                 |
| ----------------------- | ----------------------------------------------------------- |
| `api-patterns`          | REST, GraphQL, tRPC                                         |
| `nodejs-best-practices` | Node.js async, modules                                      |
| `python-patterns`       | Python standards, FastAPI                                   |
| `go-patterns`           | Go frameworks, gRPC, buf                                    |
| `rust-pro`              | Rust patterns, systems                                      |
| `typescript-expert`     | Strict-mode TS, OpenAPI→TS generation, SDK type design, Zod |

### Database

| Skill             | Description                 |
| ----------------- | --------------------------- |
| `database-design` | Schema design, optimization |

### Cloud & Infrastructure

| Skill                   | Description               |
| ----------------------- | ------------------------- |
| `deployment-procedures` | CI/CD, deploy workflows   |
| `server-management`     | Infrastructure management |

### Testing & Quality

| Skill                   | Description              |
| ----------------------- | ------------------------ |
| `testing-patterns`      | Jest, Vitest, strategies |
| `webapp-testing`        | E2E, Playwright          |
| `tdd-workflow`          | Test-driven development  |
| `code-review-checklist` | Code review standards    |
| `lint-and-validate`     | Linting, validation      |

### Security

| Skill                   | Description              |
| ----------------------- | ------------------------ |
| `vulnerability-scanner` | Security auditing, OWASP |
| `red-team-tactics`      | Offensive security       |

### Architecture & Planning

| Skill           | Description                |
| --------------- | -------------------------- |
| `app-builder`   | Full-stack app scaffolding |
| `architecture`  | System design patterns     |
| `plan-writing`  | Task planning, breakdown   |
| `brainstorming` | Socratic questioning       |

### Mobile

| Skill           | Description           |
| --------------- | --------------------- |
| `mobile-design` | Mobile UI/UX patterns |

### Game Development

| Skill              | Description           |
| ------------------ | --------------------- |
| `game-development` | Game logic, mechanics |

### SEO & Growth

| Skill              | Description                   |
| ------------------ | ----------------------------- |
| `seo-fundamentals` | SEO, E-E-A-T, Core Web Vitals |
| `geo-fundamentals` | GenAI optimization            |

### Shell/CLI

| Skill                | Description               |
| -------------------- | ------------------------- |
| `bash-linux`         | Linux commands, scripting |
| `powershell-windows` | Windows PowerShell        |

### Code Quality & Refactoring

| Skill                    | Description                              |
| ------------------------ | ---------------------------------------- |
| `clean-code`             | Coding standards (Global)                |
| `refactoring-patterns`   | Code smell detection, safe transforms    |
| `code-review-checklist`  | Code review standards                    |

### Agent & Lifecycle

| Skill                     | Description                       |
| ------------------------- | --------------------------------- |
| `behavioral-modes`        | Agent personas                    |
| `parallel-agents`         | Multi-agent patterns              |
| `mcp-builder`             | Model Context Protocol            |
| `documentation-templates` | Doc formats                       |
| `i18n-localization`       | Internationalization              |
| `performance-profiling`   | Web Vitals, optimization          |
| `systematic-debugging`    | Troubleshooting                   |
| `bmad-lifecycle`          | BMAD phase knowledge & contracts  |
| `intelligent-routing`     | Task routing & agent coordination |

---

## 🔄 Workflows (18)

Slash command procedures. Invoke with `/command`.

| Command               | Description                            |
| --------------------- | -------------------------------------- |
| `/brainstorm`         | Socratic discovery                     |
| `/create`             | Create new features                    |
| `/debug`              | Debug issues                           |
| `/deploy`             | Deploy application                     |
| `/enhance`            | Improve existing code                  |
| `/orchestrate`        | Multi-agent coordination               |
| `/plan`               | Task breakdown                         |
| `/preview`            | Preview changes                        |
| `/status`             | Check project status                   |
| `/test`               | Run tests                              |
| `/ui-ux-pro-max`      | Design with 50 styles                  |
| `/reviewer`           | Scan code, generate task queue         |
| `/discovery`          | BMAD Phase 1 — Socratic brief          |
| `/prd`                | BMAD Phase 2 — PRD from brief          |
| `/architecture-bmad`  | BMAD Phase 3 — Architecture + ADRs     |
| `/stories`            | BMAD Phase 4 — Story card batch        |
| `/sprint`             | BMAD Phase 5 — Sprint board            |
| `/close-sprint`       | BMAD — Close sprint, archive artifacts |

---

## 🎯 Skill Loading Protocol

```plaintext
User Request → Skill Description Match → Load SKILL.md
                                            ↓
                                    Read references/
                                            ↓
                                    Read scripts/
```

### Skill Structure

```plaintext
skill-name/
├── SKILL.md           # (Required) Metadata & instructions
├── scripts/           # (Optional) Python/Bash scripts
├── references/        # (Optional) Templates, docs
└── assets/            # (Optional) Images, logos
```

### Enhanced Skills (with scripts/references)

| Skill               | Files | Coverage                            |
| ------------------- | ----- | ----------------------------------- |
| `ui-ux-pro-max`     | 27    | 50 styles, 21 palettes, 50 fonts    |
| `app-builder`       | 20    | Full-stack scaffolding              |

---

## � Scripts (2)

Master validation scripts that orchestrate skill-level scripts.

### Master Scripts

| Script          | Purpose                                 | When to Use              |
| --------------- | --------------------------------------- | ------------------------ |
| `checklist.py`  | Priority-based validation (Core checks) | Development, pre-commit  |
| `verify_all.py` | Comprehensive verification (All checks) | Pre-deployment, releases |

### Usage

```bash
# Quick validation during development
python .agent/scripts/checklist.py .

# Full verification before deployment
python .agent/scripts/verify_all.py . --url http://localhost:3000
```

### What They Check

**checklist.py** (Core checks):

- Security (vulnerabilities, secrets)
- Code Quality (lint, types)
- Schema Validation
- Test Suite
- UX Audit
- SEO Check

**verify_all.py** (Full suite):

- Everything in checklist.py PLUS:
- Lighthouse (Core Web Vitals)
- Playwright E2E
- Bundle Analysis
- Mobile Audit
- i18n Check

For details, see [scripts/README.md](scripts/README.md)

---

## 🤖 Claude Code Integration

The `.agent/` folder is the **source of truth** for both Antigravity (Gemini) and Claude Code.
A thin adapter layer in `.claude/` makes the same agents and skills available to Claude Code.

### How It Works

```plaintext
.agent/agents/*.md     → .claude/agents/*.md         (specialist subagents, @-invokable)
.agent/workflows/*.md  → .claude/agents/wf-*.md      (workflow subagents,   @-invokable)
.agent/workflows/*.md  → .claude/commands/*.md        (slash commands,       /name invokable)
```

`$ARGUMENTS` is preserved verbatim in commands — identical syntax for both Antigravity and Claude Code.

### Files Added for Claude Code

- `CLAUDE.md` (repo root) — Claude Code entry point, @includes KNOWLEDGE.md + ARCHITECTURE.md
- `.agent/templates/CLAUDE.md` — Template provisioned to target repos on first CI deploy
- `.claude/settings.json` — MCP server config for Claude Code
- `.claude/agents/*.md` — 24 specialist agents + 18 workflow agents (generated, @-invokable)
- `.claude/commands/*.md` — 18 slash commands `/name` (generated, same source as workflows)
- `.agent/scripts/sync_claude_agents.py` — Generator script

### Skill Loading: Antigravity vs Claude Code

- **Antigravity**: reads `skills:` frontmatter → auto-loads SKILL.md on demand
- **Claude Code**: `skills:` field ignored → skill content embedded inline via `## Embedded Skills` section

### Slash Commands vs Subagents in Claude Code

Both are generated from the same `.agent/workflows/` source. Use the right one for the job:

- `/debug error message` — slash command, runs inline in current chat
- `@wf-debug` — subagent, used by orchestrator to delegate work programmatically

### Regenerating After Changes

```bash
# After editing .agent/agents/, .agent/skills/, or .agent/workflows/:
python3 .agent/scripts/sync_claude_agents.py

# Agents only (skip commands):
python3 .agent/scripts/sync_claude_agents.py --no-commands

# Single agent only:
python3 .agent/scripts/sync_claude_agents.py --agent debugger

# Preview without writing:
python3 .agent/scripts/sync_claude_agents.py --dry-run
```

### CI Distribution

`distribute-agentic-kit.yml` runs `sync_claude_agents.py` before rsync and distributes:

- `.agent/` — Antigravity Kit (unchanged)
- `.claude/agents/` — Claude Code subagents (generated)
- `.claude/commands/` — Claude Code slash commands (generated)
- `CLAUDE.md` — first-time provisioning only (target repos own their copy after that)

Triggers on changes to `.agent/**` or `.claude/**`.

### Naming Conventions in `.claude/`

- `.claude/agents/` — no prefix: specialist (`debugger.md`); `wf-` prefix: workflow (`wf-debug.md`)
- `.claude/commands/` — filename = command name (`debug.md` → `/debug`)

---

## 📊 Statistics

| Metric              | Value                         |
| ------------------- | ----------------------------- |
| **Total Agents**    | 26                            |
| **Total Skills**    | 42                            |
| **Total Workflows** | 18                            |
| **Total Scripts**   | 2 (master) + 18 (skill-level) |
| **Total Patterns**  | 10 (5 original + 5 BMAD)      |
| **Coverage**        | ~95% web/mobile development   |

---

## 🔗 Quick Reference

### Central Orchestration (CRON & Tasks)

- **Queue**: Tasks sit in the `tasks/` directory of target repositories.
- **Rules**: Routing matrix and PR formats are defined in `.agent/KNOWLEDGE.md`.
- **Producer**: `prompt/patterns/reviewer.md` scans code and writes to `tasks/` (scheduled via `distribution.yml`).
- **Consumer Methodologies**: `bugcatcher.md`, `featureforge.md`, `knowledge_updater.md`.

| Need               | Agent                    | Skills                                                   |
| ------------------ | ------------------------ | -------------------------------------------------------- |
| Web App            | `frontend-specialist`    | react-best-practices, frontend-design, tailwind-patterns |
| API / Backend      | `backend-specialist`     | api-patterns, nodejs-best-practices, database-design     |
| Go / Microservices | `crypto-go-specialist`   | go-patterns, api-patterns, architecture                  |
| Mobile             | `mobile-developer`       | mobile-design                                            |
| Game               | `game-developer`         | game-development                                         |
| Database           | `database-architect`     | database-design, prisma-expert                           |
| DevOps / CI/CD     | `devops-engineer`        | deployment-procedures, docker-expert                     |
| Security Audit     | `security-auditor`       | vulnerability-scanner, red-team-tactics                  |
| Pentesting         | `penetration-tester`     | red-team-tactics                                         |
| Testing            | `test-engineer`          | testing-patterns, tdd-workflow, webapp-testing           |
| E2E / QA           | `qa-automation-engineer` | webapp-testing, testing-patterns                         |
| Debug              | `debugger`               | systematic-debugging                                     |
| Performance        | `performance-optimizer`  | performance-profiling                                    |
| SEO / GEO          | `seo-specialist`         | seo-fundamentals, geo-fundamentals                       |
| Documentation      | `documentation-writer`   | documentation-templates                                  |
| Legacy / Refactor  | `code-archaeologist`     | clean-code, code-review-checklist                        |
| Codebase Explore   | `explorer-agent`         | —                                                        |
| Code Review        | `reviewer`               | —                                                        |
| Multi-agent        | `orchestrator`           | parallel-agents, behavioral-modes                        |
| Requirements / UX  | `product-manager`        | plan-writing, brainstorming                              |
| Strategy / Backlog | `product-owner`          | plan-writing, brainstorming                              |
| Plan               | `project-planner`        | brainstorming, plan-writing, architecture                |
| BMAD               | `analyst`                | bmad-lifecycle, plan-writing, brainstorming, architecture |

---

## 🔄 BMAD Lifecycle (Product Development)

BMAD layers structured product lifecycle on top of the existing agent system. Each phase produces a `wiki/` artifact consumed by the next, with explicit approval gates.

### Phase Flow

```
/discovery → wiki/BRIEF.md (approve)
    ↓
/prd → wiki/PRD.md (approve)
    ↓
/architecture-bmad → wiki/ARCHITECTURE.md (approve)
    ↓
/stories → tasks/[STORY]-*.md (batch of atomic cards)
    ↓
/sprint → wiki/sprints/sprint-NN.md
    ↓
Jules automation: full_cycle pattern → 1 story → 1 PR
```

### BMAD New Files

| File | Purpose |
|------|---------|
| `.agent/agents/analyst.md` | BMAD lifecycle driver — Discovery through Sprint |
| `.agent/skills/bmad-lifecycle/SKILL.md` | Phase knowledge, artifact contracts, story card format |
| `.agent/workflows/discovery.md` | `/discovery` — Phase 1 slash command |
| `.agent/workflows/prd.md` | `/prd` — Phase 2 slash command |
| `.agent/workflows/architecture-bmad.md` | `/architecture-bmad` — Phase 3 slash command |
| `.agent/workflows/stories.md` | `/stories` — Phase 4 slash command |
| `.agent/workflows/sprint.md` | `/sprint` — Phase 5 slash command |
| `.agent/wiki-templates/PRD.md` | PRD artifact template (distributed to all repos) |
| `.agent/wiki-templates/ARCHITECTURE.md` | Architecture decision template |
| `.agent/wiki-templates/EPIC.md` | Epic grouping template |
| `.agent/wiki-templates/STORY.md` | Story/task card template |
| `.agent/wiki-templates/DECISIONS.md` | ADR log template |
| `.agent/wiki-templates/GOTCHAS.md` | Codebase pitfalls template |
| `prompt/patterns/discovery.md` | Jules: PRD generation from brief |
| `prompt/patterns/story_writer.md` | Jules: story card batch generation |
| `prompt/patterns/sprint_planner.md` | Jules: sprint board generation |
| `prompt/patterns/sprint_closer.md` | Jules: auto-close sprint + archive artifacts |
| `prompt/patterns/full_cycle.md` | Jules: implement + test + debug loop + security → single PR |

### BMAD Automation Schedule (distribution.yml)

| Pattern | Agent | Schedule | Purpose |
|---------|-------|----------|---------|
| `discovery` | `analyst` | Mon 08:00 | Sync PRD from Brief |
| `story_writer` | `analyst` | Mon 09:00 | Seed new story cards |
| `sprint_planner` | `analyst` | Mon 10:00 | Update sprint board |
| `full_cycle` | `backend-specialist` | Daily 11:00 | Implement 1 story → 1 PR |
| `sprint_closer` | `analyst` | Daily 23:50 | Auto-close sprint when all tasks done |
