# 📚 REPOSITORY TECHNICAL STANDARDS & CONTEXT

This file serves as the core technical foundation and "Mental Model" for the repository. It defines engineering best practices, architectural philosophies, and the technical standards that all agents and developers must follow.

---

## 🏗 CORE PATTERNS & PHILOSOPHIES

### 1. 🧠 Wiki-First Workflow (Karpathy Method)

The **primary source of truth** for this project is the **`wiki/` directory** at the root of the repository.

- **Prose-First Specification**: Before a single line of code is written for a new feature, a high-level "Mental Model" and technical specification MUST be documented in `wiki/`.
- **Intuition Section**: Every major component in the wiki MUST contain an **"Intuition"** section. This explains the "Why", the "Gestalt", and the mathematical/logical foundations of the implementation.
- **Source of Truth Priority**: If the code and the wiki conflict, the wiki is considered the "intended behavior" (unless the code is provably more correct/recent, in which case the wiki must be updated immediately).

### 2. "Single Slice" Policy

Any complex change should be broken down into the smallest possible **functional slices**. This simplifies code review, testing, and ensures continuous integration of working code.

### 3. Test Determinism & Regression

- **Reproducibility**: Tests must be deterministic. Use fixed seeds for randomizers and favor mocks for external I/O.
- **Mandatory Regression**: Any change to business logic REQUIRES a regression test run.
- **Race Detection**: Always run Go tests with the **`-race`** flag to detect concurrency issues early.
- **Resource Safety**: To prevent memory exhaustion in constrained environments, Go agents MUST execute tests **package by package** (e.g., `go test ./pkg/foo`) rather than project-wide (`go test ./...`) where possible.
- **Test-Driven Bug Fixes**: When fixing a bug, you MUST first write a failing test that reproduces the issue before implementing the fix.

---

## 🐹 GO-SPECIFIC STANDARDS

### 1. Concurrency & Synchronization

- **High-Performance Patterns**: Priority is given to lock-free or fine-grained locking. Use `puzpuzpuz/xsync` for highly contended maps.
- **Locking**: Use `sync.Mutex` or `sync.RWMutex` only when absolutely unavoidable. Always document why a lock is necessary.
- **Safety**: Strict control over goroutine leaks. Always use `context.Context` for cancellation and timeouts.
- **Graceful Shutdown**: Implement timeouts for all waiting loops during shutdown to prevent infinite blocking.

### 2. Error Handling & Contextual Logging

- **Contextual Errors**: Always wrap errors with context: `fmt.Errorf("operation failed: %w", err)`. Never return "naked" errors from intermediate layers.
- **No Silencing**: Never discard errors silently (`_ = err`) without an explicit comment explaining the safety.
- **No Panics**: `panic` is strictly reserved for fatal initialization failures (e.g., missing critical config). Never use it in business logic.

### 3. Clean Build & Dependency Policy

- **Standard Library First**: Default to the Go standard library for core functionality.
- **Internal Ecosystem Pride**: Check `github.com/QuoteSystemX/model-ML` before adding external libraries. Much of the business infrastructure is already modeled there.
- **Zero-Dependency Bias**: Do NOT introduce new third-party dependencies unless absolutely critical. Justify any new dependency in the PR description.
- **Private Modules**: Repository access is managed via the `QuoteSystemX` organization. Ensure `GOPRIVATE` is configured for `github.com/QuoteSystemX/*`.

---

## 📝 DEVELOPMENT WORKFLOW

### 1. Conventional Commits & Release-Please

All repository changes are governed by semantic versioning via `release-please`. Therefore, **every Pull Request Title** MUST strictly match the [Conventional Commits](https://www.conventionalcommits.org/) format: `<type>(<scope>): <description>`.

- `feat`: New features, extending public APIs (`[FEAT]`, `[STORY]` tasks).
- `fix`: Bug fixes, logic corrections, panic resolutions (`[BUG]` tasks).
- `chore`: Maintenance, updates, audit reports, or tech debt (`[CHORE]`, `[SECURITY]`, `[INFRA]` tasks).
- `test`: Adding or correcting tests (`[TEST]`, `[QA]` tasks).
- `perf`: Performance improvements and memory optimizations (`[PERF]` tasks).
- `docs`: Modifying wiki or readme (`[DOCS]` tasks).
- `refactor`: Code restructuring without behavior change (`[REFACTOR]` tasks).
- `db`: Database schema, migration, index changes (`[DB]` tasks).

> **CRITICAL**: The text of the PR Title becomes the squash commit message. Agents MUST NOT use custom prefixes in PR titles. Deviation will break automated changelong generation.

### 2. PR Cleanup & Surgical Edits

- **Fix In-Place**: Prefer updating existing code over rewriting from scratch. Avoid creating parallel logic paths.
- **Dead Code Prevention**: Completely remove old functions/types when replacing them. No "zombie" code allowed.
- **Pre-Commit Checks**: Always run `go fmt ./...` and `go mod tidy` before creating a PR.

#### 🚫 FORBIDDEN FILES IN ANY PR (MANDATORY CLEANUP BEFORE `git add`)

Agents MUST run the following check and remove ALL matches before staging files:

```bash
# Find and delete all garbage files before committing
find . \
  -not -path './.git/*' \
  \( \
    -name "*.orig"       \
    -o -name "*.bak"     \
    -o -name "*.tmp"     \
    -o -name "*.swp"     \
    -o -name "*.swo"     \
    -o -name "*.diff"    \
    -o -name "*.patch"   \
    -o -name "*~"        \
    -o -name "PLAN.md"   \
    -o -name "*.log"     \
    -o -name ".DS_Store" \
    -o -name "Thumbs.db" \
    -o -name "__pycache__" \
    -o -name "*.pyc"     \
  \) -print -delete
```

| Forbidden Pattern | Why It Appears | Action |
| :--- | :--- | :--- |
| `*.orig`, `*.bak` | Editor/merge artifacts | DELETE before `git add` |
| `*.diff`, `*.patch` | Debug remnants from agents | DELETE before `git add` |
| `*.tmp`, `*~`, `*.swp` | Editor temp files | DELETE before `git add` |
| `PLAN.md` (root) | Orchestrator planning file | DELETE after implementation |
| `*.log` | Runtime debug output | DELETE — never commit logs |
| `__pycache__/`, `*.pyc` | Python bytecode | DELETE — add to `.gitignore` |
| `.DS_Store`, `Thumbs.db` | OS metadata | DELETE — add to `.gitignore` |
| `install_*.sh` (if auto-generated) | DevOps scripts from agents | REVIEW — only commit if intentional |

**Verification (MANDATORY before PR):**

```bash
# Must return ZERO results — if not, clean up first
git diff --name-only HEAD | grep -E "\.(orig|bak|tmp|diff|patch|log|pyc)$|~$|PLAN\.md"
```

> 🔴 **If the above command returns ANY result → DO NOT create PR. Clean up first.**

### 3. Task Management (Orchestration)

- **Active Task Queue**: The primary directory for pending work is **`tasks/`** at the root of the repository. Tasks are Markdown files created by users or the `REVIEWER` agent.
- **Task Producer**: Tasks should be highly decomposed. If a feature is large, the `REVIEWER` agent will split it into multiple `tasks/YYYY-MM-DD-slug.md` files.
- **Pickup Matrix**: Agents are completely decentralized and only pick up tasks matching their expertise (using tag matching).

  | Task Tag | Commit Type | Primary Agent(s) | Secondary Agent(s) | Notes |
  | :--- | :--- | :--- | :--- | :--- |
  | `[FEAT]` | `feat` | `backend-specialist`, `frontend-specialist` | `go-specialist`, `crypto-go-architect`, `orchestrator` | Primary implementors by domain |
  | `[STORY]` | `feat` | `backend-specialist`, `frontend-specialist`, `orchestrator` | `go-specialist`, `crypto-go-architect` | Treat identically to `[FEAT]` |
  | `[BUG]` | `fix` | `debugger` | `backend-specialist`, `test-engineer`, `qa-automation-engineer` | test-engineer writes regression after fix; qa validates E2E |
  | `[TEST]` | `test` | `test-engineer` | `qa-automation-engineer` | qa-automation for E2E/Playwright suites |
  | `[PERF]` | `perf` | `performance-optimizer` | `backend-specialist`, `go-specialist` | go-specialist for Go-specific profiling |
  | `[SECURITY]` | `chore` | `security-auditor` | `penetration-tester` | pentest for active exploit validation |
  | `[REFACTOR]` | `refactor` | `go-specialist`, `code-archaeologist` | `backend-specialist` | code-archaeologist for legacy/unknown code |
  | `[DOCS]` | `docs` | `documentation-writer` | `explorer-agent` | explorer discovers gaps; writer fills them |
  | `[DB]` | `feat` | `database-architect` | `backend-specialist` | schema, migration, index, query optimization |
  | `[INFRA]` | `chore` | `devops-engineer` | `security-auditor` | CI/CD, deploy, server, monitoring |
  | `[QA]` | `test` | `qa-automation-engineer` | `test-engineer` | E2E suites, regression pipelines, Playwright |
  | `[CHORE]` | `chore` | `project-planner` | `analyst`, `code-archaeologist` | Planning cards, tech debt, architecture ADRs |
  | `[EPIC]` | `feat` | `analyst` | — | Grouping card only, NOT directly executable |

- **Agent Capability Map** (all 24 agents):

  | Agent | Primary Labels | Role in Ecosystem |
  | :--- | :--- | :--- |
  | `backend-specialist` | `[FEAT]`, `[STORY]`, `[BUG]`, `[PERF]` | Core implementor for server/API logic |
  | `frontend-specialist` | `[FEAT]`, `[STORY]` | UI/UX implementation, React/Next.js |
  | `go-specialist` | `[FEAT]`, `[PERF]`, `[REFACTOR]` | Go language, gRPC, concurrency, high-performance services |
  | `crypto-specialist` | `[FEAT]`, `[SECURITY]` | TON/blockchain, DEX, exchange integration, financial math |
  | `crypto-go-architect` | `[FEAT]`, `[STORY]` | Go + Crypto system design, pipeline architecture, glue layer |
  | `debugger` | `[BUG]` | Root cause analysis, systematic investigation |
  | `test-engineer` | `[TEST]`, `[BUG]` (regression) | Unit/integration tests, TDD |
  | `qa-automation-engineer` | `[QA]`, `[TEST]`, `[BUG]` (E2E) | Playwright, Cypress, E2E regression pipelines |
  | `security-auditor` | `[SECURITY]` | OWASP, supply chain, zero trust |
  | `penetration-tester` | `[SECURITY]` (exploit validation) | Active attack simulation, red team |
  | `performance-optimizer` | `[PERF]` | Profiling, Core Web Vitals, bundle analysis |
  | `database-architect` | `[DB]` | Schema design, migrations, query optimization |
  | `devops-engineer` | `[INFRA]` | CI/CD, deploy, server management |
  | `documentation-writer` | `[DOCS]` | README, API docs, wiki sync |
  | `code-archaeologist` | `[REFACTOR]`, `[CHORE]` | Legacy code analysis, modernization |
  | `explorer-agent` | `[DOCS]` (discovery) | Codebase audit, wiki gap detection |
  | `analyst` | `[STORY]` (write), `[EPIC]` | BMAD lifecycle: discovery → sprint |
  | `orchestrator` | `[STORY]`, `[FEAT]` (multi-agent) | Coordinates parallel agent execution |
  | `project-planner` | `[CHORE]` | Task decomposition, architecture planning |
  | `product-manager` | — | Requirements, user stories (human-facing) |
  | `product-owner` | — | Backlog prioritization, roadmap (human-facing) |
  | `mobile-developer` | `[FEAT]` (mobile) | React Native, Flutter |
  | `game-developer` | `[FEAT]` (games) | Unity, Godot, Phaser |
  | `seo-specialist` | `[CHORE]` (SEO) | Core Web Vitals, GEO, AI search |
  | `rest-api-designer` | `[FEAT]` (API) | REST / OpenAPI design, spec-first development |
  | `grpc-architect` | `[FEAT]` (API) | gRPC / Protobuf design, streaming patterns |
  | `git-master` | `[INFRA]` (git) | Merge conflict resolution, repository recovery, history archaeology |
  | `k8s-engineer` | `[INFRA]` (k8s) | Helm, Operators, RBAC, HPA/VPA, Ingress, namespace isolation |
  | `ai-engineer` | `[FEAT]` (AI) | LLM integration, RAG pipelines, tool use, embeddings, evaluation |
  | `wiki-architect` | `[DOCS]` (wiki) | Mental Models, Intuition sections, ADRs, Prose-First, drift detection |
  | `data-engineer` | `[FEAT]` (data) | ETL/ELT pipelines, dbt, Airflow, Kafka streaming, ClickHouse analytics, data modeling |

- **Execution Protocol**:
  - At the start of a session, agents MUST check the `tasks/` directory for cards matching their domain.
  - Agents use `task.md` (in the `.agent` session metadata) to track their *current* session's progress.
  - After creating the PR, the agent MUST delete the corresponding `tasks/*.md` card.
- **Audit Reports**: If the `tasks/` queue is empty and discovery yielded zero candidates, produce an Audit Report.
- **Agent Quality Labels**: When creating a PR, agents MUST add the label `agent-generated` and `agent:<name>` (e.g. `agent:debugger`). Human reviewers then add one quality label: `agent:excellent` / `agent:ok` / `agent:revised` / `agent:rejected`. Scores are aggregated weekly into `wiki/agent-scores.md`.

### 4. BMAD Phase Rules

The BMAD lifecycle adds structured product development on top of the task queue system.

- **Phase Gate Enforcement**: No BMAD phase may begin without the previous phase's artifact existing in `wiki/`. Agents MUST NOT skip phases.
- **Artifact Immutability**: Once a phase artifact has an approval marker, only the `analyst` agent may modify it, and only via a new PR.
- **[STORY] = [FEAT] for routing**: Agents picking up `[STORY]` cards treat them identically to `[FEAT]` cards. Same routing logic, same PR conventions.
- **[EPIC] cards are non-executable**: `[EPIC]` cards group stories for tracking only. They are never picked up by execution agents (backend-specialist, etc.).
- **Sprint board as execution priority**: If `wiki/sprints/sprint-NN.md` exists, execution agents should respect the sprint priority order when selecting tasks from `tasks/`.
- **BMAD artifacts in wiki/**: All BMAD phase artifacts (BRIEF.md, PRD.md, ARCHITECTURE.md, sprints/) live in the repository's `wiki/` directory. Templates are in `.agent/wiki-templates/`.

---

## 🛠 TIPS & TRICKS

- **Relative Links**: Always use relative paths for internal documentation (e.g., `../wiki/api.md`).
- **Emoji Markers**: Use 🧪 for tests, 🐞 for bugs, ⚡ for performance to separate logical blocks.
- **Boundaries**: Use ✅ **Always do**, 🚫 **Never do** blocks to clearly define constraints for complex tasks.
