# Unified Agent Kit Architecture

> Comprehensive AI Agent Capability Expansion Toolkit

---

## 📋 Overview

Unified Agent Kit is a modular system consisting of:

- **39 Specialist Agents** - Role-based AI personas
- **55 Skills** - Domain-specific knowledge modules
- **21 Workflows** - Slash command procedures
- **1 MCP Server** - `skill-server` Go binary (skills_load, skills_list, skills_search)
- **Core Infrastructure** - Bus, Router, Telemetry, Dashboard, **Resilience Chain**
- **Autonomous SRE** - Incident Watcher, War Room Manager
- **Intelligence Layer** - Council of Sages (Multi-agent Consensus), Global Brain

---

## 🏗️ Directory Structure

```plaintext
.agent/
├── ARCHITECTURE.md          # This file
├── KNOWLEDGE.md             # Global Rules, Context, and Orchestration Standards
├── agents/                  # Specialist Agents profiles (.md) — with profile: frontmatter
├── skills/                  # Skills (Domain-specific knowledge modules)
├── workflows/               # Slash Commands for Unified Agent (+ Local triggers)
├── rules/                   # Global Rules (GEMINI.md)
├── scripts/                 # Master Validation Scripts
│   ├── lib/                 # Core Infrastructure Libraries
│   │   ├── paths.py         # Dynamic path resolution
│   │   ├── common.py        # Atomic JSON, logging, and shared utilities
│   │   └── resilience.py    # Self-healing and error handling logic
│   ├── status_report.py     # Workspace Health Dashboard
│   ├── drift_detector.py    # Documentation vs Code sync
│   ├── guardrail_monitor.py # Safety and budget enforcement
│   ├── bus_manager.py       # Context Bus (DTO) management
│   └── visualize_deps.py    # Automated Mermaid dependency visualization
└── skill-server/            # Go MCP binary (skills_load, skills_list, skills_search)
    ├── main.go
    ├── go.mod
    ├── Makefile
    ├── skill-server.sh      # Platform launcher (auto-detects OS/ARCH)
    └── bin/                 # Pre-built binaries (linux-amd64, linux-arm64)
```

### 📊 Dependency Map
<!-- DEPENDENCY_GRAPH_START -->
```mermaid
graph TD
  adr_generator --> argparse
  agent_skill_auditor --> lib
  analyze_efficiency --> collections
  arbitrator --> bus_manager
  arbitrator --> lib
  auto_preview --> argparse
  auto_preview --> signal
  autonomous_fuzzer --> random
  autonomous_reviewer_cron --> drift_detector
  autonomous_reviewer_cron --> lib
  autonomous_reviewer_cron --> status_report
  batch_runner --> argparse
  bus_debugger --> lib
  bus_manager --> argparse
  bus_manager --> lib
  bus_manager --> typing
  business_dashboard --> rich
  chaos_monkey --> lib
  chaos_monkey --> random
  checklist --> argparse
  checklist --> doc_healer
  checklist --> lib
  checklist --> prompt_optimizer
  checklist --> status_report
  checklist --> task_tracer
  checklist --> typing
  checklist --> visualize_deps
  conflict_resolver --> collections
  conflict_resolver --> lib
  context_autofill --> lib
  db --> sql
  db --> sqlite
  db_security --> sql
  discovery_brain_sync --> lib
  discovery_brain_sync --> semantic_brain_engine
  distill_context --> argparse
  doc_healer --> drift_detector
  doc_healer --> lib
  drift_detector --> argparse
  experience_distiller --> lib
  experience_distiller --> semantic_brain_engine
  generate_adr --> lib
  grafana_manager --> argparse
  grafana_manager --> resilience
  grafana_manager --> typing
  guardrail_monitor --> fnmatch
  guardrail_monitor --> lib
  handlers_bmad --> exec
  handlers_bmad --> filepath
  handlers_bmad --> mcp
  handlers_discovery -->  Then scan the first 512 bytes of SKILL.md for the keyword.
  skillPath := filepath.Join(skillsDir, name, 
  handlers_discovery --> filepath
  handlers_discovery --> mcp
  handlers_gov -->  Actually execute based on command type
 switch target.CommandType {
 case 
  handlers_gov -->  Security fixes require fewer votes for agility
  Status:      
  handlers_gov --> %d
  handlers_gov --> %d votes - %s
  handlers_gov --> filepath
  handlers_gov --> mcp
  handlers_hooks --> mcp
  handlers_infra --> %s at %s

  handlers_infra --> exec
  handlers_infra --> filepath
  handlers_infra --> mcp
  handlers_jobs --> filepath
  handlers_jobs --> mcp
  handlers_knowledge --> 
  handlers_knowledge --> exec
  handlers_knowledge --> filepath
  handlers_knowledge --> mcp
  handlers_v3_test --> filepath
  handlers_v3_test --> mcp
  handlers_v3_test --> tmp
  helpers --> filepath
  helpers --> mcp
  hooks_test -->  Call loadItem which triggers on_read
 _, err = h.loadItem(fullPath)
 if err != nil {
  t.Fatalf(
  hooks_test -->  Create docs dir first so Watch can add it
 docsDir := filepath.Join(tempDir, 
  hooks_test -->  Create file
 fullPath := filepath.Join(tempDir, relPath)
 os.MkdirAll(filepath.Dir(fullPath), 0755)
 os.WriteFile(fullPath, []byte(
  hooks_test -->  Register hook
 relPath := 
  hooks_test -->  Verify job created
 var count int
 err = db.conn.QueryRow(
  hooks_test -->  Wait for hook to trigger and job to be created
 success := false
 timeout := time.After(10 * time.Second)
 tick := time.Tick(500 * time.Millisecond)
 for {
  select {
  case <-timeout:
   t.Fatal(
  hooks_test --> Modify file
 fullPath := filepath.Join(tempDir, relPath)
 t.Logf(
  hooks_test --> filepath
  incident_watcher --> bus_manager
  incident_watcher --> lib
  indexer --> filepath
  indexer --> fsnotify
  indexer_test -->  Create a test file
 docsDir := filepath.Join(tempDir, 
  indexer_test -->  Search for 
  indexer_test -->  Setup structure
 dirs := []string{
  indexer_test -->  Test porter stemming (security -> secur)
  results, _ = idx.Search(
  indexer_test -->  Verify all 3 files are indexed
 var count int
 err = db.conn.QueryRow(
  indexer_test --> filepath
  install_hooks --> lib
  install_hooks --> shutil
  intent_validator --> lib
  knowledge_synergy --> argparse
  knowledge_synergy --> lib
  main -->  --- Agents Tools ---
 s.AddTool(mcp.NewTool(
  main -->  --- Architecture & Status ---

 s.AddTool(mcp.NewTool(
  main -->  --- BMAD Automation ---
 s.AddTool(mcp.NewTool(
  main -->  --- Council of Sages ---
 s.AddTool(mcp.NewTool(
  main -->  --- Infrastructure & Ops ---
 s.AddTool(mcp.NewTool(
  main -->  --- Jobs & Workflows ---
 s.AddTool(mcp.NewTool(
  main -->  --- Knowledge Tools ---
 s.AddTool(mcp.NewTool(
  main -->  --- Logging & Observability ---
 s.AddTool(mcp.NewTool(
  main -->  --- Resource Hooks ---
 s.AddTool(mcp.NewTool(
  main -->  --- Skills Tools ---
 s.AddTool(mcp.NewTool(
  main -->  Data Retention initialization
 if *retentionDays > 0 {
  h.db.SetSetting(
  main -->  Ensure essential tables are populated
 _ = h.db.SaveProposal(&CouncilProposal{
  ID:        
  main -->  Graceful shutdown
  srv := &http.Server{Addr: addr}
  go func() {
   if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
    fmt.Fprintf(os.Stderr, 
  main -->  Helper to wrap handlers with RBAC and Telemetry
 withRBAC := func(toolName string, hdlr func(context.Context, mcp.CallToolRequest) (*mcp.CallToolResult, error)) func(context.Context, mcp.CallToolRequest) (*mcp.CallToolResult, error) {
  return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
   start := time.Now()
   agent := 
  main -->  Indexer initialization
 if *indexDirs != 
  main -->  RBAC Check
   allowed, err := h.db.CheckPermission(agent, toolName)
   if err != nil || !allowed {
    if toolName == 
  main -->  SSE log streaming (simulated)
  http.HandleFunc(
  main --> filepath
  main --> http
  main --> mcp
  main --> readiness probes.
  http.HandleFunc(
  main --> server
  main --> signal
  main_test --> filepath
  main_test --> mcp
  maintenance --> filepath
  metrics_dashboard --> rich
  model_router --> argparse
  post_mortem_runner --> lib
  pr_audit --> lib
  pre_commit_review --> conflict_resolver
  pre_commit_review --> lib
  pre_commit_review --> status_report
  pre_commit_review --> task_tracer
  prompt_optimizer --> collections
  prompt_optimizer --> lib
  quality_tracker --> argparse
  quality_tracker --> collections
  quality_tracker --> urllib
  rollback_task --> argparse
  rollback_task --> lib
  sandbox_runner --> ast
  sandbox_runner --> tempfile
  security_scan --> argparse
  security_scan --> lib
  self_healer --> traceback
  semantic_brain_engine --> lib
  semantic_brain_engine --> typing
  semantic_experience --> lib
  session_manager --> argparse
  session_manager --> typing
  skill_factory --> argparse
  skill_factory --> lib
  skill_versioning --> argparse
  status_report --> drift_detector
  status_report --> lib
  sync_claude_agents --> argparse
  sync_claude_agents --> visualize_deps
  task_helper --> argparse
  task_miner --> argparse
  task_miner --> lib
  task_tracer --> lib
  verify_all --> argparse
  verify_all --> typing
  visualize_deps --> lib
  war_room_manager --> bus_manager
  war_room_manager --> lib
  workers --> exec
  workers --> json
  workers_test --> filepath
```
<!-- DEPENDENCY_GRAPH_END -->

## 📁 Prompt Library Hub Features (Repository Root)

```plaintext
├── prompt/patterns/         # Execution Methodologies (featureforge, bugcatcher, reviewer)
├── tasks/                   # Active Agent Task Queue
├── .github/distribution.yml # CRON Task Distribution Map
└── .github/profiles.yml     # Distribution Profiles (go-service, web-app, data-platform, mobile, game)
```

## 🛠️ Workspace Management & Hygiene

- `python3 .agent/scripts/status_report.py` - Unified Dashboard (Tech + Business)
- `python3 .agent/scripts/task_helper.py` - Task card generator for `tasks/`
- `python3 .agent/scripts/drift_detector.py` - Wiki vs Code drift detection
- `python3 .agent/scripts/metrics_dashboard.py` - Real-time agent telemetry
- `python3 .agent/scripts/business_dashboard.py` - Story card progress tracking
- `python3 .agent/skills/lint-and-validate/scripts/lint_runner.py` - Janitor & Linter

## 🤖 Agents (36)

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
| `go-specialist`          | Go, gRPC, Concurrency, Perf | go-patterns, godoc-patterns, api-patterns, architecture          |
| `crypto-specialist`      | TON, DEX, Exchange, Trading | api-patterns, architecture                                       |
| `crypto-go-architect`    | Go + Crypto system design   | go-patterns, api-patterns, architecture, brainstorming           |
| `devops-engineer`        | CI/CD, Docker              | deployment-procedures, server-management                          |
| `security-auditor`       | Security compliance        | vulnerability-scanner, red-team-tactics                           |
| `penetration-tester`     | Offensive security         | red-team-tactics                                                  |
| `test-engineer`          | Testing strategies         | testing-patterns, tdd-workflow, webapp-testing                    |
| `debugger`               | Root cause analysis        | systematic-debugging                                              |
| `red-team`               | Adversarial Auditor        | red-team-tactics, vulnerability-scanner                           |
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
| `git-master`             | Git internals & recovery   | git-master, bash-linux, systematic-debugging, clean-code           |
| `k8s-engineer`           | Kubernetes platform        | k8s-patterns, deployment-procedures, server-management, bash-linux |
| `ai-engineer`            | AI / LLM systems           | llm-patterns, python-patterns, api-patterns, systematic-debugging  |
| `wiki-architect`         | Knowledge architecture     | wiki-writing, documentation-templates, brainstorming               |
| `data-engineer`          | Data pipelines & analytics | data-patterns, database-design, python-patterns, bash-linux        |
| `sre-engineer`           | Reliability engineering    | observability-patterns, k8s-patterns, deployment-procedures       |
| `cloud-engineer`         | Multi-cloud infrastructure | cloud-patterns, terraform-patterns, deployment-procedures         |
| `visual-designer`      | UI/UX aesthetics          | frontend-design, web-design-guidelines                            |
| `release-manager`     | Versioning & SemVer       | git-master, testing-patterns, lint-and-validate                   |

---

## 🧩 Skills (53)

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

| Skill                    | Description                                                           |
| ------------------------ | --------------------------------------------------------------------- |
| `deployment-procedures`  | CI/CD, deploy workflows                                               |
| `server-management`      | Infrastructure management                                             |
| `terraform-patterns`     | HCL modules, state management, plan/apply safety, checkov, terratest  |
| `observability-patterns` | OTel, Prometheus, Grafana, Loki, Jaeger, SLO/SLI, Alertmanager       |

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
| `shared-context`         | Context Bus & DTO management      |
| `telemetry`              | Execution metrics & cost tracking |
| `bmad-lifecycle`          | BMAD phase knowledge & contracts  |
| `intelligent-routing`     | Task routing & agent coordination |

---

## 🔄 Workflows (21)

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
| `/release`            | Production release cycle               |
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

## 📜 Scripts (23)

Master validation scripts that orchestrate skill-level scripts.

### Master Scripts

| Script                | Purpose                                 | When to Use              |
| --------------------- | --------------------------------------- | ------------------------ |
| `checklist.py`        | Priority-based validation (Core checks) | Development, pre-commit  |
| `verify_all.py`       | Comprehensive verification (All checks) | Pre-deployment, releases |
| `model_router.py`     | Dynamic task complexity routing (L1-L3) | Every subagent call      |
| `bus_manager.py`      | Context Bus administration (Push/Pull)  | Debugging, inspection    |
| `business_dashboard.py` | Feature-level progress tracking (Rich) | /status, sprint review   |
| `metrics_dashboard.py` | Technical observability (CLI Monitor)   | Monitoring               |
| `drift_detector.py`   | Documentation lag detection             | /status, /release        |
| `analyze_efficiency.py` | Performance & Cost (Token usage)       | Monthly audit            |
| `distill_context.py`  | Long-context optimization (RAG/Extract) | Shared Context Bus       |
| `batch_runner.py`     | Fan-out / Fan-in parallel execution    | Multi-agent tasks        |
| `experience_distiller.py` | Lesson learned archiving (30 days), `--auto-export` to global brain | Maintenance, post-merge  |
| `autonomous_reviewer_cron.py` | Daily codebase audit — drift, infra, roadmap gaps → task cards | self-driving-ops.yml (daily) |
| `guardrail_monitor.py` | Budget & Token safety watchdog         | Runtime monitoring       |
| `post_mortem_runner.py` | Failure analysis & Lesson generation   | After task failure       |
| `doc_healer.py`      | Self-healing Documentation        | after code changes       |
| `knowledge_synergy.py` | Cross-project knowledge sync    | Post-Mortem, ADR export  |
| `incident_watcher.py`  | Autonomous failure detection    | Runtime, CI/CD           |
| `war_room_manager.py`  | Multi-agent incident resolution | After incident           |
| `arbitrator.py`        | Multi-agent consensus manager   | Architecture decisions   |
| `resource_forecaster.py` | Token & time budget prediction | Phase 22/23 Gateway Audit |
| `hidden_war_room.py`   | 4-participant agent debate      | Strategic thinking & Veto |
| `truth_validator.py`   | Cross-source truth check        | Requirement validation    |
| `personality_adapter.py` | Style & DNA adaptation         | User stylistic alignment  |
| `requirement_expander.py` | Hybrid knowledge expansion     | /prd, /architecture      |
| `auto_adr_drafter.py`  | Autonomous ADR drafting        | Phase 3 Architecture     |
| `browser_resilience.py` | Browser connectivity manager     | Every web/browser task   |
| `output_bridge.py`     | Agent output validator & Red-Team Gate | Every final response     |
| `model_router.py`     | Unified Provider Router (Gemini/Claude) | Every subagent call      |
| `self_healer.py`       | Autonomous Script Repair Wrapper       | Tool execution           |
| `skill_discovery.py`   | JIT Skill Acquisition (URL Fetcher)    | Knowledge expansion      |
| `sandbox_runner.py`    | Safe Code Sandbox (AST + Isolation)    | Untrusted code execution |
| `predictive_watcher.py` | Predictive DevOps (Auto-ADR)          | Post-session maintenance |
| `obsidian_sync.py`    | Obsidian Wiki-to-Code Bridge          | Every final response     |
| `model_validator.py`  | Mental Model Architecture Validator   | Every final response     |
| `governance_gate.py`  | Wiki-First Enforcement Sentinel       | Every final response     |
| `knowledge_miner.py`  | Retroactive Knowledge Archeologist    | Maintenance              |
| `walkthrough_assembler.py` | Auto-documentation assembler   | Maintenance              |
| `task_sync.py`        | Task status synchronizer        | Maintenance              |

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

### 🧩 Domain-specific Validation Scripts (Skill-level)

These scripts are located within specific skill folders and are used for domain-level auditing.

| Script | Skill | Purpose |
| :--- | :--- | :--- |
| `i18n_checker.py` | `i18n-localization` | Detect hardcoded strings & missing translations |
| `react_performance_checker.py` | `nextjs-react-expert` | Automated performance audit for React/Next.js |
| `convert_rules.py` | `nextjs-react-expert` | Convert and validate optimization rules |
| `seo_checker.py` | `seo-fundamentals` | Verify meta tags, headers, and SEO basics |

---

## 🛠️ CLI Tool Reference

The following tools are available in `.agent/scripts/` for maintenance and safety:

### `checklist.py`

Master validation runner.

- `python3 .agent/scripts/checklist.py .` - Run all core checks.
- `--fix` - Automatically fix simple configuration and directory issues.
- `--url <URL>` - Include performance and E2E checks.

### `guardrail_monitor.py`

Safety and budget watchdog.

- `--check-cmd "<command>"` - Validate a command against block/warn lists. Handles pipes, subshells, and detects secret leaks.
- `--check-file "<path>"` - Check if a file is protected.

### `experience_distiller.py`

Learning and knowledge maintenance.

- `python3 .agent/scripts/experience_distiller.py` - Archive lessons older than 30 days.
- `--skill <name>` - Filter and display lessons for a specific skill (searches active and archives).
- `--list-skills` - List all unique skill tags in the knowledge base.

### `bus_manager.py`

Context Bus administration.

- `push --id <ID> --type <TYPE> --author <NAME> --content '<JSON>'` - Push data to the shared bus. Alerts if telemetry exceeds budget.
- `wait --id <ID> --timeout <sec>` - Wait for a specific object to appear.
- `list`, `peek`, `delete`, `clear` - Manage bus objects.

### `visualize_deps.py`

Dependency Graph Generator.

- `python3 .agent/scripts/visualize_deps.py` - Scans imports and updates the Mermaid diagram in `ARCHITECTURE.md`.

### `status_report.py`

Workspace Health Dashboard.

- `python3 .agent/scripts/status_report.py` - Shows the Health Score (0-100%) based on drift, logs, security, and tests.

### `generate_adr.py`

Architecture Decision Record Generator.

- `python3 .agent/scripts/generate_adr.py "<Title>" "<Context>" "<Decision>"` - Creates a new ADR in `wiki/decisions/`.

### `post_mortem_runner.py`

Failure Analysis Tool.

- `python3 .agent/scripts/post_mortem_runner.py` - Analyzes recent logs and suggests a lesson learned.

### `pre_commit_review.py`

Git Hook Reviewer.

- `python3 .agent/scripts/pre_commit_review.py` - Checks staged diffs against historical lessons in `LESSONS_LEARNED.md`.

### `rollback_task.py`

Task & State Undo.

- `python3 .agent/scripts/rollback_task.py [--author <name>]` - Reverts git changes and cleans up the context bus.

### `test_factory.py`

Unit Test Generator.

- `python3 .agent/scripts/test_factory.py <target_file>` - Generates basic test files for Python and Go.

### `vulnerability_patcher.py`

Security Auto-patch Helper.

- `python3 .agent/scripts/vulnerability_patcher.py <type> <file> <context>` - Formats a secure fix request for an agent.

### `bus_debugger.py`

Interactive Bus Inspector.

- `python3 .agent/scripts/bus_debugger.py` - Interactive shell to list and peek at bus objects.

### `task_tracer.py`

Git-to-Task Traceability.

- `python3 .agent/scripts/task_tracer.py` - Links staged changes to active cards in `tasks/`. Triggered by `pre-commit`.

### `prompt_optimizer.py`

Cost & Prompt Efficiency.

- `python3 .agent/scripts/prompt_optimizer.py` - Analyzes telemetry and suggests token reductions.

### `conflict_resolver.py`

Bus Arbitration.

- `python3 .agent/scripts/conflict_resolver.py` - Detects ID collisions and state conflicts.

### `semantic_experience.py`

Contextual Knowledge Search.

- `python3 .agent/scripts/semantic_experience.py <query>` - Searches LESSONS_LEARNED.md using keyword overlap.

### `doc_healer.py`

Self-healing Documentation.

- `python3 .agent/scripts/doc_healer.py` - Analyzes code and updates ARCHITECTURE.md for new files.

---

## 🤖 Claude Code Integration

The `.agent/` folder is the **source of truth** for both Unified Agent (Gemini) and Claude Code.
A thin adapter layer in `.claude/` makes the same agents and skills available to Claude Code.

### How It Works

```plaintext
.agent/agents/*.md     → .claude/agents/*.md         (specialist subagents, @-invokable)
.agent/workflows/*.md  → .claude/agents/wf-*.md      (workflow subagents,   @-invokable)
.agent/workflows/*.md  → .claude/commands/*.md        (slash commands,       /name invokable)
```

`$ARGUMENTS` is preserved verbatim in commands — identical syntax for both Unified Agent and Claude Code.

### Files Added for Claude Code

- `CLAUDE.md` (repo root) — Claude Code entry point, @includes KNOWLEDGE.md + ARCHITECTURE.md
- `.agent/templates/CLAUDE.md` — Template provisioned to target repos on first CI deploy
- `.claude/settings.json` — MCP server config + `"agent": "orchestrator"` for auto-routing
- `~/.claude/.mcp.json` — User-level MCP config (skill-server at absolute path)
- `.claude/agents/*.md` — 31 specialist agents + 18 workflow agents (generated, @-invokable)
- `.claude/commands/*.md` — 18 slash commands `/name` (generated, same source as workflows)
- `.agent/scripts/sync_claude_agents.py` — Generator script (`--profile`, `--agent`, `--dry-run`)
- `.agent/skill-server/` — Go MCP binary source + pre-built linux binaries

### Skill Loading: Unified Agent vs Claude Code

- **Unified Agent**: reads `skills:` frontmatter → auto-loads SKILL.md on demand
- **Claude Code (Variant A)**: dynamic loading — generated agents get a `> **Skills** — read these files` pointer block; no inline embedding. Eliminates duplication and the 100-line truncation limit.
- **skill-server MCP** (Variant C): Go binary exposes `skills_load`, `skills_list`, `skills_search` tools via stdio JSON-RPC. Configured in `.claude/settings.json` (project) and `~/.claude/.mcp.json` (user).

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

# Distribution profile — only agents relevant for the target repo type:
python3 .agent/scripts/sync_claude_agents.py --profile go-service
python3 .agent/scripts/sync_claude_agents.py --profile web-app
python3 .agent/scripts/sync_claude_agents.py --profile data-platform
python3 .agent/scripts/sync_claude_agents.py --profile mobile
```

### CI Distribution

`distribute-agentic-kit.yml` runs `sync_claude_agents.py` (optionally with `--profile`) before rsync and distributes:

- `.agent/` — Unified Agent Kit (unchanged)
- `.claude/agents/` — Claude Code subagents (generated, filtered by profile if set)
- `.claude/commands/` — Claude Code slash commands (generated)
- `.agent/skill-server/bin/` — Pre-built Go binaries (linux-amd64, linux-arm64)
- `CLAUDE.md` — first-time provisioning only (target repos own their copy after that)

Triggers on changes to `.agent/**` or `.claude/**`. Binaries are built by `build-skill-server.yml` and committed to the repo, so distribution requires no Go toolchain in target repos.

**Profile-based distribution** — add `--profile <name>` to the rsync step to exclude domain-irrelevant agents. Profiles defined in `.github/profiles.yml`.

### Naming Conventions in `.claude/`

- `.claude/agents/` — no prefix: specialist (`debugger.md`); `wf-` prefix: workflow (`wf-debug.md`)
- `.claude/commands/` — filename = command name (`debug.md` → `/debug`)

---

## 📊 Statistics

| Metric              | Value                                           |
| ------------------- | ----------------------------------------------- |
| **Total Agents**    | 39                                              |
| **Total Skills**    | 55                                              |
| **Total Workflows** | 21                                              |
| **Total Scripts**   | 24                                              |
| **Total Patterns**  | 10 (5 original + 5 BMAD)                        |
| **MCP Servers**     | 1 (`skill-server` Go binary — stdio transport)  |
| **Coverage**        | ~95% web/mobile/backend/infra development       |

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
| Go / Microservices | `go-specialist`          | go-patterns, godoc-patterns, api-patterns, architecture  |
| Crypto / TON / DEX | `crypto-specialist`      | api-patterns, architecture                               |
| Go + Crypto system | `crypto-go-architect`    | go-patterns, api-patterns, architecture, brainstorming   |
| Mobile             | `mobile-developer`       | mobile-design                                            |
| Game               | `game-developer`         | game-development                                         |
| Database           | `database-architect`     | database-design, prisma-expert                           |
| DevOps / CI/CD     | `devops-engineer`        | deployment-procedures, docker-expert                     |
| Kubernetes / K8s   | `k8s-engineer`           | k8s-patterns, deployment-procedures, terraform-patterns  |
| Observability/SRE  | `sre-engineer`           | observability-patterns, k8s-patterns                     |
| Git / Conflicts    | `git-master`             | git-master, bash-linux                                   |
| AI / LLM           | `ai-engineer`            | llm-patterns, python-patterns                            |
| Wiki / Knowledge   | `wiki-architect`         | wiki-writing, documentation-templates                    |
| Data Pipelines     | `data-engineer`          | data-patterns, database-design, python-patterns          |
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

## 🛡️ Autonomous SRE & Intelligence (Auto-SRE)

The kit implements a self-healing loop inspired by high-reliability systems.

### 1. The Reflex Loop (War Room)

- **Detection**: `incident_watcher.py` monitors all exit codes.
- **Elevation**: Failures are pushed to the Context Bus as `incident` objects.
- **Resolution**: `war_room_manager.py` invokes a triad of agents (Debugger, Test Engineer, Orchestrator) to generate a `proposed_fix`.
- **Git-Ops**: In user-less mode, the system creates a `fix/inc-ID` branch and commits verified fixes autonomously.

### 2. Council of Sages (Consensus)

Mandatory multi-agent review for architectural decisions.

- **Workflow**: Draft → Challenge (Red-Team) → Defense (Proposer) → Verdict (Arbitrator).
- **Enforcement**: ADRs without an `approved` verdict on the bus are blocked by the Pre-Commit Gate.

### 3. Global Knowledge Layer (Global Brain)

Knowledge shared across repositories and AI tools (Gemini, Claude Code).

- **Storage**: Neutral path `~/.agent_knowledge/` (configurable via `AGENT_GLOBAL_ROOT`).
- **Sync**: `knowledge_synergy.py` exports repository ADRs to the global lessons base.
- **Search**: `experience_distiller.py` performs multi-root search (Local + Global).

---

## 🧠 Cognitive Automation & Unified Provider Routing (Phase 2026)

The kit implements a provider-agnostic cognitive layer that bridges Antigravity (Gemini) and Cloud Core (Claude).

### 1. Unified Multi-Model Router

- **Logic**: Automatically detects the active environment (`AGENT_PROVIDER`) and maps task complexity (L1-L3) to the most cost-effective yet capable model.
- **Failover**: Implements cross-provider fallback (e.g., if Gemini is rate-limited, it routes to Claude).

### 2. Autonomous Self-Healing & JIT Skills

- **Self-Repair**: `self_healer.py` wraps critical script execution. If a failure is detected, it generates a "Repair DTO" in the Context Bus for the `@debugger` agent to fulfill.
- **JIT Acquisition**: `skill_discovery.py` allows agents to ingest external documentation on-the-fly, synthesizing new skills in `.agent/skills/temp/` without human intervention.

### 3. Safety Gate & AST Sandbox

- **Red-Team Gate**: Instrumented in `output_bridge.py`. Critical infrastructure or security changes are automatically audited by `security_scan.py` and `threat_modeler.py` before completion.
- **Safe Execution**: `sandbox_runner.py` uses AST static analysis to block dangerous code and executes in a restricted, temporary environment.

---

## 🆕 Recent Additions

| File | Description |
| --- | --- |
| `.agent/scripts/grafana_manager.py` | Grafana dashboard CRUD — create/update panels, datasources, alerts via REST API. |
| `.agent/scripts/incident_watcher.py` | Incident Watcher — monitors process exit codes and pushes failures to Context Bus. |
| `.agent/scripts/war_room_manager.py` | War Room Manager — orchestrates Debugger + Test-Engineer + Orchestrator triad for autonomous incident resolution. |
| `.agent/scripts/arbitrator.py` | Council of Sages judge — produces a `verdict` on architectural decisions from multi-agent debate. |
| `.agent/scripts/skill_factory.py` | Generates SKILL.md scaffolding for new skills with correct frontmatter and structure. |
| `.agent/scripts/task_miner.py` | Mines `wiki/ROADMAP.md` for untracked backlog items and converts them to `tasks/` cards. |
| `.agent/scripts/pr_audit.py` | Deep PR audit — runs security, drift, conflict, and quality checks on staged changes. |
| `.agent/scripts/chaos_monkey.py` | Deliberate fault injection for resilience testing (run on throwaway branches only). |
| `.agent/scripts/semantic_brain_engine.py` | TF-IDF semantic search engine over LESSONS_LEARNED and global knowledge base. |
| `.agent/scripts/agent_skill_auditor.py` | Ensures every agent has mandatory skills (clean-code) and valid SKILL.md metadata. |
| `.agent/scripts/ci_auto_fixer.py` | Auto-healing: detects failing CI jobs and proposes targeted fix commits. |
| `.agent/scripts/context_autofill.py` | Autonomous context investigator — pulls ADRs, lessons, and bus state before an agent starts. |
| `.agent/scripts/discovery_brain_sync.py` | Syncs discovery output to Semantic Brain for future semantic search queries. |
| `.agent/scripts/intent_validator.py` | Phase 18 gate — detects architectural conflicts before implementation begins. |
| `.agent/scripts/ambiguity_detector.py` | Socratic gate — identifies vague or ambiguous requirements before coding. |
| `.agent/scripts/impact_analyzer.py` | Estimates blast radius of a change across the codebase before execution. |
| `.agent/scripts/code_polisher.py` | Applies senior-level polish: removes dead code, enforces naming conventions, simplifies logic. |
| `.agent/scripts/failure_correlator.py` | Cross-references recent failures with LESSONS_LEARNED to detect repeated mistakes. |
| `.agent/scripts/threat_modeler.py` | STRIDE-based threat modeler — generates threat model for a given component or PR. |
| `.agent/scripts/resource_optimizer.py` | Economic audit — identifies high-token operations and suggests cheaper alternatives. |
| `.agent/scripts/ghost_prototyper.py` | Creates throwaway proof-of-concept branches to validate architectural hypotheses. |
| `.agent/scripts/autonomous_fuzzer.py` | Generates randomized edge-case inputs to stress-test functions and APIs. |
| `.agent/scripts/resource_forecaster.py` | Predicts token and wall-clock budget for a task before execution (Phase 23 gate). |
| `.agent/scripts/hidden_war_room.py` | 4-participant strategic debate: Optimist, Skeptic, Advocate, Arbitrator — for major decisions. |
| `.agent/scripts/truth_validator.py` | Cross-references Local Brain, global knowledge, and external sources for contradictions. |
| `.agent/scripts/personality_adapter.py` | Detects user stylistic DNA (Minimalism/Pragmatism) and adapts agent response style. |
| `.agent/scripts/requirement_expander.py` | Cascading knowledge retrieval — expands terse requirements into detailed specs with feedback loop. |
| `.agent/scripts/auto_adr_drafter.py` | Autonomous ADR drafting triggered by Phase 22/23 architectural decision gates. |
| `.agent/scripts/browser_resilience.py` | Browser connectivity manager for WSL/macOS — CDP, DNS gateway, headless fallback. |
| `.agent/scripts/output_bridge.py` | Mandatory Agent Output Gateway — validates 5-section report structure and syncs to bus. |
| `.agent/scripts/walkthrough_assembler.py` | Assembles session walkthrough log from task.md and bus events into wiki/archive. |
| `.agent/scripts/task_sync.py` | Synchronises task card status (open/in-progress/done) with Context Bus state. |
| `.agent/scripts/obsidian_validator.py` | Validates Obsidian-format wiki links and frontmatter before distribution to target repos. |
| `.agent/scripts/autonomous_reviewer_cron.py` | Daily codebase audit — drift, infra gaps, roadmap items → auto-creates task cards. |
| `.agent/scripts/security_scan.py` | OWASP static scanner — detects hardcoded secrets, dangerous patterns (eval, shell=True, weak hashes). |
| `.agent/scripts/session_manager.py` | Session Manager - Antigravity Kit |
| `paperclip-plugin/node_modules/` | System module for node_modules. |
| `paperclip-plugin/node_modules/finalhandler/index.js` | ! |
| `paperclip-plugin/node_modules/hasown/index.js` | System module for index.js. |
| `paperclip-plugin/node_modules/json-schema-typed/draft_2020_12.js` | @generated |
| `paperclip-plugin/node_modules/side-channel/index.d.ts` | System module for index.d.ts. |
| `paperclip-plugin/node_modules/is-promise/index.d.ts` | System module for index.d.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/mini/schemas.ts` | System module for schemas.ts. |
| `paperclip-plugin/node_modules/express/lib/express.js` | ! |
| `paperclip-plugin/node_modules/once/once.js` | System module for once.js. |
| `paperclip-plugin/node_modules/qs/lib/formats.js` | System module for formats.js. |
| `paperclip-plugin/node_modules/es-errors/index.d.ts` | System module for index.d.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/el.d.ts` | System module for el.d.ts. |
| `paperclip-plugin/node_modules/call-bind-apply-helpers/index.js` | System module for index.js. |
| `paperclip-plugin/node_modules/negotiator/lib/language.js` | negotiator |
| `paperclip-plugin/node_modules/ajv/lib/standalone/instance.ts` | System module for instance.ts. |
| `paperclip-plugin/node_modules/range-parser/index.js` | ! |
| `paperclip-plugin/node_modules/zod/v4/locales/az.d.ts` | System module for az.d.ts. |
| `paperclip-plugin/node_modules/gopd/gOPD.js` | System module for gOPD.js. |
| `paperclip-plugin/node_modules/negotiator/lib/encoding.js` | negotiator |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/validation/index.ts` | System module for index.ts. |
| `paperclip-plugin/node_modules/cookie-signature/index.js` | Module dependencies. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/core/id.ts` | System module for id.ts. |
| `paperclip-plugin/node_modules/zod/v3/standard-schema.d.ts` | The Standard Schema interface. |
| `paperclip-plugin/node_modules/ipaddr.js/lib/ipaddr.js` | System module for ipaddr.js. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2017.arraybuffer.d.ts` | !  |
| `paperclip-plugin/node_modules/zod/v4/locales/uk.d.ts` | System module for uk.d.ts. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/discriminator/index.ts` | System module for index.ts. |
| `paperclip-plugin/node_modules/zod-to-json-schema/postesm.ts` | System module for postesm.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.scripthost.d.ts` | !  |
| `paperclip-plugin/node_modules/es-errors/type.js` | System module for type.js. |
| `paperclip-plugin/node_modules/zod/v4/locales/ta.d.ts` | System module for ta.d.ts. |
| `paperclip-plugin/node_modules/zod/src/v3/external.ts` | System module for external.ts. |
| `paperclip-plugin/node_modules/zod/v4/core/schemas.d.ts` | System module for schemas.d.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/pt.js` | System module for pt.js. |
| `paperclip-plugin/node_modules/express/lib/response.js` | ! |
| `paperclip-plugin/node_modules/zod/v3/helpers/parseUtil.js` | System module for parseUtil.js. |
| `paperclip-plugin/node_modules/ajv/lib/runtime/validation_error.ts` | System module for validation_error.ts. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/unevaluated/unevaluatedItems.ts` | System module for unevaluatedItems.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2015.proxy.d.ts` | !  |
| `.agent/mcp-server/indexer.go` | System module for indexer.go. |
| `paperclip-plugin/node_modules/cross-spawn/index.js` | System module for index.js. |
| `paperclip-plugin/node_modules/es-object-atoms/RequireObjectCoercible.d.ts` | System module for RequireObjectCoercible.d.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/uz.js` | System module for uz.js. |
| `paperclip-plugin/node_modules/hasown/index.d.ts` | System module for index.d.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/classic/coerce.ts` | System module for coerce.ts. |
| `paperclip-plugin/node_modules/react/cjs/react-jsx-runtime.development.js` | @license React |
| `paperclip-plugin/node_modules/zod/v4/locales/ar.d.ts` | System module for ar.d.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2020.promise.d.ts` | !  |
| `paperclip-plugin/node_modules/zod/src/v3/benchmarks/object.ts` | System module for object.ts. |
| `paperclip-plugin/node_modules/loose-envify/index.js` | System module for index.js. |
| `paperclip-plugin/node_modules/escape-html/index.js` | ! |
| `paperclip-plugin/node_modules/router/index.js` | ! |
| `paperclip-plugin/node_modules/ipaddr.js/lib/ipaddr.js.d.ts` | System module for ipaddr.js.d.ts. |
| `paperclip-plugin/node_modules/loose-envify/custom.js` | envify compatibility |
| `paperclip-plugin/node_modules/math-intrinsics/isNegativeZero.d.ts` | System module for isNegativeZero.d.ts. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/applicator/items.ts` | System module for items.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.d.ts` | !  |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2024.d.ts` | !  |
| `paperclip-plugin/node_modules/zod/v4/core/versions.js` | System module for versions.js. |
| `paperclip-plugin/node_modules/gopd/index.d.ts` | System module for index.d.ts. |
| `paperclip-plugin/node_modules/zod/v4/core/core.d.ts` | System module for core.d.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2017.string.d.ts` | !  |
| `paperclip-plugin/node_modules/undici-types/errors.d.ts` | System module for errors.d.ts. |
| `paperclip-plugin/node_modules/ajv/.runkit_example.js` | System module for .runkit_example.js. |
| `paperclip-plugin/node_modules/zod/v3/helpers/typeAliases.d.ts` | System module for typeAliases.d.ts. |
| `paperclip-plugin/node_modules/cross-spawn/lib/parse.js` | System module for parse.js. |
| `paperclip-plugin/node_modules/gopd/gOPD.d.ts` | System module for gOPD.d.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/el.js` | System module for el.js. |
| `paperclip-plugin/node_modules/zod/v4/classic/external.js` | System module for external.js. |
| `paperclip-plugin/node_modules/zod/src/v4/locales/ko.ts` | System module for ko.ts. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/dynamic/recursiveAnchor.ts` | System module for recursiveAnchor.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2023.full.d.ts` | !  |
| `paperclip-plugin/node_modules/react/cjs/react.shared-subset.production.min.js` | @license React |
| `paperclip-plugin/node_modules/qs/lib/parse.js` | System module for parse.js. |
| `paperclip-plugin/node_modules/iconv-lite/encodings/utf16.js` | System module for utf16.js. |
| `paperclip-plugin/node_modules/react/umd/react.profiling.min.js` | @license React |
| `paperclip-plugin/node_modules/undici-types/global-dispatcher.d.ts` | System module for global-dispatcher.d.ts. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/jtd/ref.ts` | System module for ref.ts. |
| `paperclip-plugin/node_modules/ajv/lib/refs/jtd-schema.ts` | System module for jtd-schema.ts. |
| `paperclip-plugin/node_modules/undici-types/mock-client.d.ts` | System module for mock-client.d.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/hu.js` | System module for hu.js. |
| `paperclip-plugin/node_modules/proxy-addr/index.js` | ! |
| `paperclip-plugin/node_modules/zod/v4/locales/ps.d.ts` | System module for ps.d.ts. |
| `paperclip-plugin/node_modules/object-inspect/util.inspect.js` | System module for util.inspect.js. |
| `paperclip-plugin/node_modules/dunder-proto/set.d.ts` | System module for set.d.ts. |
| `paperclip-plugin/node_modules/iconv-lite/lib/index.js` | System module for index.js. |
| `paperclip-plugin/node_modules/typescript/lib/lib.esnext.iterator.d.ts` | !  |
| `paperclip-plugin/node_modules/debug/src/browser.js` | eslint-env browser |
| `paperclip-plugin/node_modules/side-channel-list/list.d.ts` | System module for list.d.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2023.array.d.ts` | !  |
| `paperclip-plugin/node_modules/undici-types/webidl.d.ts` | These types are not exported, and are only used internally |
| `paperclip-plugin/node_modules/es-object-atoms/ToObject.d.ts` | System module for ToObject.d.ts. |
| `paperclip-plugin/node_modules/zod/v3/locales/en.d.ts` | System module for en.d.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2022.full.d.ts` | !  |
| `paperclip-plugin/node_modules/undici-types/websocket.d.ts` | / <reference types="node" /> |
| `paperclip-plugin/node_modules/zod/src/v4/locales/da.ts` | System module for da.ts. |
| `paperclip-plugin/node_modules/zod/v3/helpers/errorUtil.d.ts` | System module for errorUtil.d.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/is.js` | System module for is.js. |
| `paperclip-plugin/node_modules/es-errors/eval.js` | System module for eval.js. |
| `.agent/mcp-server/helpers.go` | System module for helpers.go. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/applicator/properties.ts` | System module for properties.ts. |
| `paperclip-plugin/node_modules/zod/v4/mini/coerce.d.ts` | System module for coerce.d.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2017.typedarrays.d.ts` | !  |
| `paperclip-plugin/node_modules/zod/v4/locales/da.js` | System module for da.js. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/jtd/values.ts` | System module for values.ts. |
| `paperclip-plugin/node_modules/iconv-lite/encodings/sbcs-data.js` | System module for sbcs-data.js. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/jtd/enum.ts` | System module for enum.ts. |
| `paperclip-plugin/node_modules/react/cjs/react-jsx-runtime.profiling.min.js` | @license React |
| `paperclip-plugin/node_modules/negotiator/index.js` | ! |
| `paperclip-plugin/node_modules/call-bound/index.d.ts` | System module for index.d.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/tr.js` | System module for tr.js. |
| `paperclip-plugin/node_modules/typescript/lib/lib.webworker.iterable.d.ts` | !  |
| `paperclip-plugin/node_modules/zod/src/v4/mini/coerce.ts` | System module for coerce.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/cs.js` | System module for cs.js. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2019.intl.d.ts` | !  |
| `paperclip-plugin/node_modules/iconv-lite/types/encodings.d.ts` | --------------------------------------------------------------------------------------------- |
| `paperclip-plugin/node_modules/typescript/lib/_tsserver.js` | !  |
| `paperclip-plugin/node_modules/fast-uri/lib/schemes.js` | System module for schemes.js. |
| `paperclip-plugin/node_modules/zod/v4/locales/hu.d.ts` | System module for hu.d.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/cs.d.ts` | System module for cs.d.ts. |
| `paperclip-plugin/node_modules/depd/lib/browser/index.js` | ! |
| `paperclip-plugin/node_modules/zod/v4/locales/he.d.ts` | System module for he.d.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/be.js` | System module for be.js. |
| `paperclip-plugin/node_modules/zod/src/v4/locales/tr.ts` | System module for tr.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/zh-TW.js` | System module for zh-TW.js. |
| `paperclip-plugin/node_modules/ajv/lib/ajv.ts` | System module for ajv.ts. |
| `paperclip-plugin/node_modules/statuses/index.js` | ! |
| `paperclip-plugin/node_modules/body-parser/index.js` | ! |
| `paperclip-plugin/node_modules/math-intrinsics/sign.d.ts` | System module for sign.d.ts. |
| `paperclip-plugin/node_modules/side-channel-map/index.js` | System module for index.js. |
| `paperclip-plugin/node_modules/zod/src/v4/core/doc.ts` | System module for doc.ts. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/core/index.ts` | System module for index.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/locales/fr-CA.ts` | System module for fr-CA.ts. |
| `paperclip-plugin/node_modules/get-proto/index.js` | System module for index.js. |
| `paperclip-plugin/node_modules/negotiator/lib/charset.js` | negotiator |
| `paperclip-plugin/node_modules/vary/index.js` | ! |
| `paperclip-plugin/node_modules/ajv/lib/compile/jtd/types.ts` | System module for types.ts. |
| `paperclip-plugin/node_modules/typescript/lib/typingsInstaller.js` | This file is a shim which defers loading the real module until the compile cache is enabled. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/applicator/contains.ts` | System module for contains.ts. |
| `paperclip-plugin/node_modules/zod/v4/core/registries.js` | System module for registries.js. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/applicator/items2020.ts` | System module for items2020.ts. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/applicator/dependencies.ts` | System module for dependencies.ts. |
| `paperclip-plugin/node_modules/zod/v4/classic/index.js` | System module for index.js. |
| `paperclip-plugin/node_modules/math-intrinsics/constants/maxSafeInteger.d.ts` | System module for maxSafeInteger.d.ts. |
| `paperclip-plugin/node_modules/call-bind-apply-helpers/functionApply.js` | System module for functionApply.js. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es5.d.ts` | !  |
| `paperclip-plugin/node_modules/send/index.js` | ! |
| `paperclip-plugin/node_modules/math-intrinsics/isNaN.d.ts` | System module for isNaN.d.ts. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/applicator/allOf.ts` | System module for allOf.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/locales/kh.ts` | System module for kh.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2020.d.ts` | !  |
| `paperclip-plugin/node_modules/body-parser/lib/utils.js` | System module for utils.js. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/dynamic/dynamicAnchor.ts` | System module for dynamicAnchor.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2020.date.d.ts` | !  |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/jtd/properties.ts` | System module for properties.ts. |
| `paperclip-plugin/node_modules/encodeurl/index.js` | ! |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2021.intl.d.ts` | !  |
| `paperclip-plugin/node_modules/math-intrinsics/isNaN.js` | System module for isNaN.js. |
| `.agent/mcp-server/workers.go` | System module for workers.go. |
| `paperclip-plugin/node_modules/undici-types/fetch.d.ts` | based on https:github.com/Ethan-Arrowood/undici-fetch/blob/249269714db874351589d2d364a0645d5160ae71/index.d.ts (MIT license) |
| `paperclip-plugin/node_modules/math-intrinsics/round.d.ts` | System module for round.d.ts. |
| `paperclip-plugin/node_modules/react/jsx-dev-runtime.js` | System module for jsx-dev-runtime.js. |
| `paperclip-plugin/node_modules/math-intrinsics/mod.d.ts` | System module for mod.d.ts. |
| `paperclip-plugin/node_modules/json-schema-typed/draft_07.d.ts` | System module for draft_07.d.ts. |
| `paperclip-plugin/node_modules/zod/v4/core/json-schema-generator.d.ts` | System module for json-schema-generator.d.ts. |
| `paperclip-plugin/node_modules/undici-types/cache.d.ts` | System module for cache.d.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/classic/parse.ts` | System module for parse.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2019.symbol.d.ts` | !  |
| `paperclip-plugin/node_modules/zod/v4/locales/zh-TW.d.ts` | System module for zh-TW.d.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/en.js` | System module for en.js. |
| `paperclip-plugin/node_modules/math-intrinsics/mod.js` | System module for mod.js. |
| `paperclip-plugin/node_modules/zod/v4/classic/compat.d.ts` | System module for compat.d.ts. |
| `paperclip-plugin/node_modules/ip-address/src/v6/regular-expressions.ts` | System module for regular-expressions.ts. |
| `paperclip-plugin/node_modules/zod/v4/mini/schemas.d.ts` | System module for schemas.d.ts. |
| `paperclip-plugin/node_modules/es-object-atoms/RequireObjectCoercible.js` | System module for RequireObjectCoercible.js. |
| `paperclip-plugin/node_modules/side-channel/index.js` | System module for index.js. |
| `.agent/mcp-server/db_observability.go` | System module for db_observability.go. |
| `paperclip-plugin/node_modules/iconv-lite/lib/helpers/merge-exports.js` | System module for merge-exports.js. |
| `paperclip-plugin/node_modules/get-proto/Reflect.getPrototypeOf.js` | System module for Reflect.getPrototypeOf.js. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2018.asyncgenerator.d.ts` | !  |
| `paperclip-plugin/node_modules/isexe/windows.js` | System module for windows.js. |
| `paperclip-plugin/node_modules/typescript/lib/lib.esnext.disposable.d.ts` | !  |
| `paperclip-plugin/node_modules/ajv/lib/2019.ts` | System module for 2019.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/core/json-schema-processors.ts` | System module for json-schema-processors.ts. |
| `paperclip-plugin/node_modules/zod/v3/ZodError.js` | System module for ZodError.js. |
| `paperclip-plugin/node_modules/fast-deep-equal/es6/index.d.ts` | System module for index.d.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/locales/bg.ts` | System module for bg.ts. |
| `paperclip-plugin/node_modules/zod/locales/index.d.ts` | System module for index.d.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/locales/eo.ts` | System module for eo.ts. |
| `paperclip-plugin/node_modules/raw-body/index.d.ts` | System module for index.d.ts. |
| `paperclip-plugin/node_modules/body-parser/lib/types/raw.js` | ! |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/applicator/propertyNames.ts` | System module for propertyNames.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/core/versions.ts` | System module for versions.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2024.arraybuffer.d.ts` | !  |
| `paperclip-plugin/node_modules/zod/src/v4/mini/checks.ts` | System module for checks.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/hr.d.ts` | System module for hr.d.ts. |
| `paperclip-plugin/node_modules/json-schema-typed/draft_2019_09.d.ts` | System module for draft_2019_09.d.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/locales/ms.ts` | System module for ms.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/classic/schemas.ts` | System module for schemas.ts. |
| `paperclip-plugin/node_modules/parseurl/index.js` | ! |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2015.iterable.d.ts` | !  |
| `paperclip-plugin/node_modules/ajv/lib/compile/validate/subschema.ts` | System module for subschema.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2023.d.ts` | !  |
| `paperclip-plugin/node_modules/typescript/lib/lib.esnext.array.d.ts` | !  |
| `paperclip-plugin/node_modules/react/umd/react.development.js` | @license React |
| `paperclip-plugin/node_modules/has-symbols/shams.js` | System module for shams.js. |
| `paperclip-plugin/node_modules/dunder-proto/get.d.ts` | System module for get.d.ts. |
| `paperclip-plugin/node_modules/undici-types/filereader.d.ts` | / <reference types="node" /> |
| `paperclip-plugin/node_modules/undici-types/formdata.d.ts` | Based on https:github.com/octet-stream/form-data/blob/2d0f0dc371517444ce1f22cdde13f51995d0953a/lib/FormData.ts (MIT) |
| `paperclip-plugin/node_modules/body-parser/lib/types/text.js` | ! |
| `paperclip-plugin/node_modules/serve-static/index.js` | ! |
| `paperclip-plugin/node_modules/zod/v3/external.js` | System module for external.js. |
| `paperclip-plugin/node_modules/side-channel-map/index.d.ts` | System module for index.d.ts. |
| `paperclip-plugin/node_modules/zod/v4/classic/compat.js` | Zod 3 compat layer |
| `paperclip-plugin/node_modules/zod/src/v4/locales/km.ts` | System module for km.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/tr.d.ts` | System module for tr.d.ts. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/jtd/nullable.ts` | System module for nullable.ts. |
| `paperclip-plugin/node_modules/ajv/lib/runtime/ucs2length.ts` | https:mathiasbynens.be/notes/javascript-encoding |
| `paperclip-plugin/node_modules/iconv-lite/lib/index.d.ts` | --------------------------------------------------------------------------------------------- |
| `paperclip-plugin/node_modules/zod/src/v3/benchmarks/datetime.ts` | System module for datetime.ts. |
| `paperclip-plugin/node_modules/zod/v4/mini/iso.js` | System module for iso.js. |
| `paperclip-plugin/node_modules/zod/v3/helpers/util.js` | System module for util.js. |
| `paperclip-plugin/node_modules/ajv/lib/compile/validate/index.ts` | System module for index.ts. |
| `.agent/mcp-server/db_hooks.go` | System module for db_hooks.go. |
| `paperclip-plugin/node_modules/undici-types/cookies.d.ts` | / <reference types="node" /> |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/validation/enum.ts` | System module for enum.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.esnext.float16.d.ts` | !  |
| `paperclip-plugin/node_modules/zod/src/v4/locales/ta.ts` | System module for ta.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/lt.d.ts` | System module for lt.d.ts. |
| `paperclip-plugin/node_modules/es-errors/range.js` | System module for range.js. |
| `paperclip-plugin/node_modules/express/index.js` | ! |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2017.sharedmemory.d.ts` | !  |
| `paperclip-plugin/node_modules/undici-types/retry-handler.d.ts` | System module for retry-handler.d.ts. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/jtd/metadata.ts` | System module for metadata.ts. |
| `paperclip-plugin/node_modules/express/lib/view.js` | ! |
| `paperclip-plugin/node_modules/zod/v4/classic/schemas.d.ts` | System module for schemas.d.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/mini/index.ts` | System module for index.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/ms.js` | System module for ms.js. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2015.symbol.wellknown.d.ts` | !  |
| `paperclip-plugin/node_modules/fast-deep-equal/es6/index.js` | System module for index.js. |
| `paperclip-plugin/node_modules/ajv/lib/refs/json-schema-2020-12/index.ts` | System module for index.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/ka.d.ts` | System module for ka.d.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/th.js` | System module for th.js. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/applicator/patternProperties.ts` | System module for patternProperties.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/ca.js` | System module for ca.js. |
| `paperclip-plugin/node_modules/etag/index.js` | ! |
| `paperclip-plugin/node_modules/zod/src/v3/benchmarks/ipv4.ts` | System module for ipv4.ts. |
| `paperclip-plugin/node_modules/react/jsx-runtime.js` | System module for jsx-runtime.js. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/applicator/oneOf.ts` | System module for oneOf.ts. |
| `paperclip-plugin/node_modules/zod/v4/core/index.d.ts` | System module for index.d.ts. |
| `paperclip-plugin/node_modules/math-intrinsics/floor.d.ts` | System module for floor.d.ts. |
| `paperclip-plugin/node_modules/ajv/lib/compile/jtd/serialize.ts` | System module for serialize.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2016.d.ts` | !  |
| `paperclip-plugin/node_modules/zod/src/v4/locales/nl.ts` | System module for nl.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/classic/checks.ts` | System module for checks.ts. |
| `paperclip-plugin/node_modules/cross-spawn/lib/util/readShebang.js` | System module for readShebang.js. |
| `paperclip-plugin/node_modules/undici-types/dispatcher.d.ts` | System module for dispatcher.d.ts. |
| `paperclip-plugin/node_modules/es-define-property/index.d.ts` | System module for index.d.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/es.d.ts` | System module for es.d.ts. |
| `paperclip-plugin/node_modules/object-inspect/example/circular.js` | System module for circular.js. |
| `paperclip-plugin/node_modules/zod/v4/locales/kh.d.ts` | System module for kh.d.ts. |
| `paperclip-plugin/node_modules/accepts/index.js` | ! |
| `paperclip-plugin/node_modules/es-errors/uri.js` | System module for uri.js. |
| `paperclip-plugin/node_modules/json-schema-typed/draft_2020_12.d.ts` | System module for draft_2020_12.d.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/locales/uk.ts` | System module for uk.ts. |
| `paperclip-plugin/node_modules/zod/v4/core/util.js` | System module for util.js. |
| `paperclip-plugin/node_modules/isexe/index.js` | System module for index.js. |
| `paperclip-plugin/node_modules/typescript/lib/lib.dom.d.ts` | !  |
| `paperclip-plugin/node_modules/math-intrinsics/max.js` | System module for max.js. |
| `paperclip-plugin/node_modules/zod/v4/mini/coerce.js` | System module for coerce.js. |
| `paperclip-plugin/node_modules/zod/v4/locales/eo.d.ts` | System module for eo.d.ts. |
| `paperclip-plugin/node_modules/isexe/mode.js` | System module for mode.js. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/validation/limitContains.ts` | System module for limitContains.ts. |
| `paperclip-plugin/node_modules/debug/src/common.js` | System module for common.js. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2020.full.d.ts` | !  |
| `paperclip-plugin/node_modules/undici-types/header.d.ts` | The header type declaration of `undici`. |
| `paperclip-plugin/node_modules/zod/src/v4/classic/errors.ts` | System module for errors.ts. |
| `paperclip-plugin/node_modules/zod/v3/helpers/util.d.ts` | System module for util.d.ts. |
| `paperclip-plugin/node_modules/unpipe/index.js` | ! |
| `.agent/mcp-server/handlers_hooks.go` | System module for handlers_hooks.go. |
| `paperclip-plugin/node_modules/fast-deep-equal/react.js` | System module for react.js. |
| `paperclip-plugin/node_modules/ajv/lib/compile/validate/defaults.ts` | System module for defaults.ts. |
| `paperclip-plugin/node_modules/has-symbols/index.js` | System module for index.js. |
| `paperclip-plugin/node_modules/shebang-regex/index.js` | System module for index.js. |
| `paperclip-plugin/node_modules/mime-db/index.js` | ! |
| `paperclip-plugin/node_modules/zod/v4/locales/nl.js` | System module for nl.js. |
| `paperclip-plugin/node_modules/zod/v4/locales/yo.js` | System module for yo.js. |
| `paperclip-plugin/node_modules/qs/lib/stringify.js` | System module for stringify.js. |
| `paperclip-plugin/node_modules/undici-types/agent.d.ts` | System module for agent.d.ts. |
| `paperclip-plugin/node_modules/merge-descriptors/index.js` | System module for index.js. |
| `paperclip-plugin/node_modules/zod/v3/index.js` | System module for index.js. |
| `paperclip-plugin/node_modules/zod/mini/index.js` | System module for index.js. |
| `paperclip-plugin/node_modules/ajv/lib/compile/validate/dataType.ts` | System module for dataType.ts. |
| `paperclip-plugin/node_modules/zod/src/v3/index.ts` | System module for index.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2024.regexp.d.ts` | !  |
| `paperclip-plugin/node_modules/zod/v4/core/util.d.ts` | System module for util.d.ts. |
| `paperclip-plugin/node_modules/undici-types/client.d.ts` | System module for client.d.ts. |
| `paperclip-plugin/node_modules/ajv-formats/src/limit.ts` | System module for limit.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/locales/ota.ts` | System module for ota.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/ja.d.ts` | System module for ja.d.ts. |
| `paperclip-plugin/node_modules/undici-types/file.d.ts` | Based on https:github.com/octet-stream/form-data/blob/2d0f0dc371517444ce1f22cdde13f51995d0953a/lib/File.ts (MIT) |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2024.sharedmemory.d.ts` | !  |
| `.agent/mcp-server/handlers_bmad.go` | System module for handlers_bmad.go. |
| `paperclip-plugin/node_modules/typescript/lib/lib.dom.asynciterable.d.ts` | !  |
| `paperclip-plugin/node_modules/zod/src/v4/locales/hr.ts` | System module for hr.ts. |
| `paperclip-plugin/node_modules/ajv/lib/compile/ref_error.ts` | System module for ref_error.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2021.d.ts` | !  |
| `paperclip-plugin/node_modules/ajv/lib/2020.ts` | System module for 2020.ts. |
| `paperclip-plugin/node_modules/eventsource/src/index.ts` | System module for index.ts. |
| `paperclip-plugin/node_modules/zod/v4/mini/index.js` | System module for index.js. |
| `paperclip-plugin/node_modules/zod/v3/errors.js` | System module for errors.js. |
| `paperclip-plugin/node_modules/zod/v4/classic/from-json-schema.js` | System module for from-json-schema.js. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/validation/limitProperties.ts` | System module for limitProperties.ts. |
| `paperclip-plugin/node_modules/fast-deep-equal/es6/react.d.ts` | System module for react.d.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/classic/iso.ts` | System module for iso.ts. |
| `paperclip-plugin/node_modules/es-object-atoms/index.js` | System module for index.js. |
| `paperclip-plugin/node_modules/zod/v4/locales/zh-CN.js` | System module for zh-CN.js. |
| `paperclip-plugin/node_modules/ajv/lib/compile/errors.ts` | System module for errors.ts. |
| `paperclip-plugin/node_modules/react/cjs/react-jsx-dev-runtime.development.js` | @license React |
| `paperclip-plugin/node_modules/zod/src/v3/types.ts` | System module for types.ts. |
| `paperclip-plugin/node_modules/es-object-atoms/ToObject.js` | System module for ToObject.js. |
| `paperclip-plugin/node_modules/react/cjs/react.production.min.js` | @license React |
| `paperclip-plugin/node_modules/side-channel-weakmap/index.d.ts` | System module for index.d.ts. |
| `paperclip-plugin/node_modules/undici-types/readable.d.ts` | System module for readable.d.ts. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/jtd/elements.ts` | System module for elements.ts. |
| `paperclip-plugin/node_modules/zod/v3/types.d.ts` | System module for types.d.ts. |
| `paperclip-plugin/node_modules/zod/v4-mini/index.d.ts` | System module for index.d.ts. |
| `paperclip-plugin/node_modules/zod/src/v3/ZodError.ts` | System module for ZodError.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/pl.d.ts` | System module for pl.d.ts. |
| `paperclip-plugin/node_modules/math-intrinsics/pow.js` | System module for pow.js. |
| `paperclip-plugin/node_modules/wrappy/wrappy.js` | Returns a wrapper function that returns a wrapped callback |
| `paperclip-plugin/node_modules/iconv-lite/encodings/sbcs-data-generated.js` | System module for sbcs-data-generated.js. |
| `paperclip-plugin/node_modules/fast-uri/eslint.config.js` | System module for eslint.config.js. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2015.symbol.d.ts` | !  |
| `paperclip-plugin/node_modules/zod/v4/locales/ar.js` | System module for ar.js. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2019.array.d.ts` | !  |
| `paperclip-plugin/node_modules/es-errors/syntax.d.ts` | System module for syntax.d.ts. |
| `paperclip-plugin/node_modules/zod/src/v3/helpers/partialUtil.ts` | System module for partialUtil.ts. |
| `paperclip-plugin/node_modules/get-proto/Object.getPrototypeOf.js` | System module for Object.getPrototypeOf.js. |
| `paperclip-plugin/node_modules/zod/v4/locales/ru.d.ts` | System module for ru.d.ts. |
| `paperclip-plugin/node_modules/has-symbols/shams.d.ts` | System module for shams.d.ts. |
| `paperclip-plugin/node_modules/es-errors/type.d.ts` | System module for type.d.ts. |
| `paperclip-plugin/node_modules/math-intrinsics/constants/maxValue.d.ts` | System module for maxValue.d.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2015.promise.d.ts` | !  |
| `paperclip-plugin/node_modules/zod/src/v4/core/core.ts` | System module for core.ts. |
| `paperclip-plugin/node_modules/zod/v4/core/to-json-schema.d.ts` | System module for to-json-schema.d.ts. |
| `paperclip-plugin/node_modules/body-parser/lib/types/json.js` | ! |
| `paperclip-plugin/node_modules/setprototypeof/index.js` | System module for index.js. |
| `paperclip-plugin/node_modules/es-object-atoms/isObject.d.ts` | System module for isObject.d.ts. |
| `paperclip-plugin/node_modules/eventsource-parser/src/types.ts` | System module for types.ts. |
| `paperclip-plugin/node_modules/undici-types/mock-errors.d.ts` | System module for mock-errors.d.ts. |
| `paperclip-plugin/node_modules/zod/src/v3/benchmarks/union.ts` | System module for union.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2017.intl.d.ts` | !  |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2019.string.d.ts` | !  |
| `paperclip-plugin/node_modules/merge-descriptors/index.d.ts` | Merges "own" properties from a source to a destination object, including non-enumerable and accessor-defined properties. It retains original values and descriptors, ensuring the destination receives a complete and accurate copy of the source's properties. |
| `paperclip-plugin/node_modules/undici-types/retry-agent.d.ts` | System module for retry-agent.d.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/core/config.ts` | System module for config.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/id.js` | System module for id.js. |
| `paperclip-plugin/node_modules/zod/v4/locales/pt.d.ts` | System module for pt.d.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/locales/es.ts` | System module for es.ts. |
| `paperclip-plugin/node_modules/ajv/lib/compile/util.ts` | System module for util.ts. |
| `paperclip-plugin/node_modules/gopd/index.js` | System module for index.js. |
| `paperclip-plugin/node_modules/zod/v3/standard-schema.js` | System module for standard-schema.js. |
| `paperclip-plugin/node_modules/loose-envify/loose-envify.js` | System module for loose-envify.js. |
| `paperclip-plugin/node_modules/undici-types/pool.d.ts` | System module for pool.d.ts. |
| `paperclip-plugin/node_modules/zod/v3/external.d.ts` | System module for external.d.ts. |
| `paperclip-plugin/node_modules/csstype/index.d.ts` | System module for index.d.ts. |
| `paperclip-plugin/node_modules/es-errors/uri.d.ts` | System module for uri.d.ts. |
| `paperclip-plugin/node_modules/undici-types/proxy-agent.d.ts` | System module for proxy-agent.d.ts. |
| `paperclip-plugin/node_modules/fast-uri/index.js` | System module for index.js. |
| `paperclip-plugin/node_modules/object-inspect/example/all.js` | System module for all.js. |
| `paperclip-plugin/node_modules/zod/v4/locales/da.d.ts` | System module for da.d.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/ko.js` | System module for ko.js. |
| `paperclip-plugin/node_modules/zod/v3/types.js` | System module for types.js. |
| `paperclip-plugin/node_modules/zod/v4/mini/parse.d.ts` | System module for parse.d.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/ps.js` | System module for ps.js. |
| `paperclip-plugin/node_modules/negotiator/lib/mediaType.js` | negotiator |
| `paperclip-plugin/node_modules/object-inspect/index.js` | System module for index.js. |
| `paperclip-plugin/node_modules/zod/src/v4/mini/iso.ts` | System module for iso.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/locales/ro.ts` | System module for ro.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2024.string.d.ts` | !  |
| `paperclip-plugin/node_modules/zod/v4/locales/sl.js` | System module for sl.js. |
| `paperclip-plugin/node_modules/fast-deep-equal/index.js` | System module for index.js. |
| `paperclip-plugin/node_modules/zod/v3/helpers/typeAliases.js` | System module for typeAliases.js. |
| `paperclip-plugin/node_modules/undici-types/eventsource.d.ts` | System module for eventsource.d.ts. |
| `paperclip-plugin/node_modules/ajv/lib/runtime/quote.ts` | System module for quote.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/yo.d.ts` | System module for yo.d.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2022.intl.d.ts` | !  |
| `paperclip-plugin/node_modules/iconv-lite/encodings/index.js` | System module for index.js. |
| `paperclip-plugin/node_modules/typescript/lib/lib.esnext.decorators.d.ts` | !  |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2017.object.d.ts` | !  |
| `paperclip-plugin/node_modules/zod/v4/locales/eo.js` | System module for eo.js. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/applicator/thenElse.ts` | System module for thenElse.ts. |
| `paperclip-plugin/node_modules/zod/v4/core/api.js` | System module for api.js. |
| `paperclip-plugin/node_modules/zod/v4/locales/index.js` | System module for index.js. |
| `paperclip-plugin/node_modules/math-intrinsics/round.js` | System module for round.js. |
| `paperclip-plugin/node_modules/math-intrinsics/isInteger.d.ts` | System module for isInteger.d.ts. |
| `paperclip-plugin/node_modules/toidentifier/index.js` | ! |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/validation/multipleOf.ts` | System module for multipleOf.ts. |
| `paperclip-plugin/node_modules/zod/src/locales/index.ts` | System module for index.ts. |
| `paperclip-plugin/node_modules/typescript/lib/tsserverlibrary.js` | !  |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/dynamic/recursiveRef.ts` | System module for recursiveRef.ts. |
| `paperclip-plugin/node_modules/js-tokens/index.js` | Copyright 2014, 2015, 2016, 2017, 2018 Simon Lydell |
| `paperclip-plugin/node_modules/math-intrinsics/floor.js` | System module for floor.js. |
| `paperclip-plugin/node_modules/zod/src/v3/benchmarks/discriminatedUnion.ts` | System module for discriminatedUnion.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2015.reflect.d.ts` | !  |
| `paperclip-plugin/node_modules/zod/src/v4/classic/external.ts` | System module for external.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2020.intl.d.ts` | !  |
| `paperclip-plugin/node_modules/typescript/lib/lib.decorators.d.ts` | !  |
| `paperclip-plugin/node_modules/ip-address/src/common.ts` | System module for common.ts. |
| `paperclip-plugin/node_modules/react/cjs/react-jsx-runtime.production.min.js` | @license React |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2021.string.d.ts` | !  |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2016.full.d.ts` | !  |
| `paperclip-plugin/node_modules/qs/lib/index.js` | System module for index.js. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/unevaluated/unevaluatedProperties.ts` | System module for unevaluatedProperties.ts. |
| `paperclip-plugin/node_modules/zod-to-json-schema/postcjs.ts` | System module for postcjs.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/fa.d.ts` | System module for fa.d.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/index.d.ts` | System module for index.d.ts. |
| `paperclip-plugin/node_modules/ajv/lib/core.ts` | System module for core.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/hy.js` | System module for hy.js. |
| `paperclip-plugin/node_modules/ee-first/index.js` | ! |
| `paperclip-plugin/node_modules/iconv-lite/encodings/utf32.js` | System module for utf32.js. |
| `paperclip-plugin/node_modules/json-schema-traverse/index.d.ts` | System module for index.d.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/core/api.ts` | System module for api.ts. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/validation/dependentRequired.ts` | System module for dependentRequired.ts. |
| `paperclip-plugin/node_modules/call-bind-apply-helpers/actualApply.js` | System module for actualApply.js. |
| `paperclip-plugin/node_modules/content-type/index.js` | ! |
| `paperclip-plugin/node_modules/ajv/lib/types/index.ts` | System module for index.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2018.intl.d.ts` | !  |
| `paperclip-plugin/node_modules/zod/v3/ZodError.d.ts` | System module for ZodError.d.ts. |
| `paperclip-plugin/node_modules/debug/src/node.js` | Module dependencies. |
| `paperclip-plugin/node_modules/ajv/lib/types/json-schema.ts` | eslint-disable @typescript-eslint/no-empty-interface |
| `paperclip-plugin/node_modules/zod/src/index.ts` | System module for index.ts. |
| `.agent/scripts/auto_preview.py` | Auto Preview - Antigravity Kit |
| `paperclip-plugin/node_modules/zod/src/v3/errors.ts` | System module for errors.ts. |
| `paperclip-plugin/node_modules/undici-types/interceptors.d.ts` | System module for interceptors.d.ts. |
| `paperclip-plugin/node_modules/math-intrinsics/isInteger.js` | System module for isInteger.js. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2019.d.ts` | !  |
| `paperclip-plugin/node_modules/zod/src/v4/locales/ps.ts` | System module for ps.ts. |
| `paperclip-plugin/node_modules/ms/index.js` | Helpers. |
| `paperclip-plugin/node_modules/fast-deep-equal/react.d.ts` | System module for react.d.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.esnext.sharedmemory.d.ts` | !  |
| `paperclip-plugin/node_modules/zod/v4/locales/ta.js` | System module for ta.js. |
| `paperclip-plugin/node_modules/typescript/lib/lib.esnext.full.d.ts` | !  |
| `paperclip-plugin/node_modules/zod/v4/mini/schemas.js` | System module for schemas.js. |
| `paperclip-plugin/node_modules/router/lib/route.js` | ! |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/next.ts` | System module for next.ts. |
| `paperclip-plugin/node_modules/ip-address/src/ipv6.ts` | eslint-disable prefer-destructuring |
| `paperclip-plugin/node_modules/ip-address/src/v6/constants.ts` | System module for constants.ts. |
| `paperclip-plugin/node_modules/setprototypeof/index.d.ts` | System module for index.d.ts. |
| `paperclip-plugin/node_modules/ajv/lib/standalone/index.ts` | System module for index.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/fi.js` | System module for fi.js. |
| `paperclip-plugin/node_modules/zod/v4/locales/no.d.ts` | System module for no.d.ts. |
| `paperclip-plugin/node_modules/zod/v4/core/parse.js` | System module for parse.js. |
| `paperclip-plugin/node_modules/type-is/index.js` | ! |
| `paperclip-plugin/node_modules/zod/v4/core/regexes.d.ts` | @deprecated CUID v1 is deprecated by its authors due to information leakage |
| `paperclip-plugin/node_modules/zod/v4/classic/errors.js` | System module for errors.js. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2022.error.d.ts` | !  |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/jtd/union.ts` | System module for union.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/locales/hu.ts` | System module for hu.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/core/registries.ts` | System module for registries.ts. |
| `.agent/mcp-server/handlers_jobs.go` | System module for handlers_jobs.go. |
| `paperclip-plugin/node_modules/zod/v4/locales/th.d.ts` | System module for th.d.ts. |
| `paperclip-plugin/node_modules/zod/index.js` | System module for index.js. |
| `paperclip-plugin/node_modules/zod/src/v4/locales/yo.ts` | System module for yo.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.webworker.asynciterable.d.ts` | !  |
| `paperclip-plugin/node_modules/math-intrinsics/sign.js` | System module for sign.js. |
| `paperclip-plugin/node_modules/zod/v4/locales/he.js` | System module for he.js. |
| `paperclip-plugin/node_modules/zod/v4/locales/km.d.ts` | System module for km.d.ts. |
| `paperclip-plugin/node_modules/undici-types/mock-pool.d.ts` | System module for mock-pool.d.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/core/standard-schema.ts` | The Standard interface. |
| `paperclip-plugin/node_modules/zod/v4/mini/external.js` | System module for external.js. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/applicator/index.ts` | System module for index.ts. |
| `paperclip-plugin/node_modules/get-proto/Object.getPrototypeOf.d.ts` | System module for Object.getPrototypeOf.d.ts. |
| `paperclip-plugin/node_modules/typescript/lib/tsserverlibrary.d.ts` | !  |
| `paperclip-plugin/node_modules/zod/src/v3/locales/en.ts` | System module for en.ts. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/validation/limitNumber.ts` | System module for limitNumber.ts. |
| `paperclip-plugin/node_modules/zod/v4/core/standard-schema.js` | System module for standard-schema.js. |
| `paperclip-plugin/node_modules/undici-types/balanced-pool.d.ts` | System module for balanced-pool.d.ts. |
| `paperclip-plugin/node_modules/zod/v4/core/versions.d.ts` | System module for versions.d.ts. |
| `paperclip-plugin/node_modules/body-parser/lib/read.js` | ! |
| `paperclip-plugin/node_modules/ajv/lib/compile/codegen/scope.ts` | System module for scope.ts. |
| `paperclip-plugin/node_modules/call-bind-apply-helpers/functionCall.js` | System module for functionCall.js. |
| `paperclip-plugin/node_modules/es-object-atoms/index.d.ts` | System module for index.d.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/locales/fr.ts` | System module for fr.ts. |
| `paperclip-plugin/node_modules/function-bind/index.js` | System module for index.js. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/validation/required.ts` | System module for required.ts. |
| `paperclip-plugin/node_modules/zod/v3/helpers/parseUtil.d.ts` | System module for parseUtil.d.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/locales/ua.ts` | System module for ua.ts. |
| `paperclip-plugin/node_modules/eventsource-parser/src/parse.ts` | EventSource/Server-Sent Events parser |
| `paperclip-plugin/node_modules/zod/v4/locales/fr.d.ts` | System module for fr.d.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2023.intl.d.ts` | !  |
| `paperclip-plugin/node_modules/zod/src/v4/core/checks.ts` | import { $ZodType } from "./schemas.js"; |
| `paperclip-plugin/node_modules/zod/v4/core/core.js` | System module for core.js. |
| `paperclip-plugin/node_modules/iconv-lite/encodings/internal.js` | System module for internal.js. |
| `paperclip-plugin/node_modules/zod/v4/classic/parse.js` | System module for parse.js. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/validation/limitItems.ts` | System module for limitItems.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2021.full.d.ts` | !  |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/validation/pattern.ts` | System module for pattern.ts. |
| `paperclip-plugin/node_modules/cross-spawn/lib/enoent.js` | System module for enoent.js. |
| `paperclip-plugin/node_modules/math-intrinsics/constants/maxArrayLength.d.ts` | System module for maxArrayLength.d.ts. |
| `paperclip-plugin/node_modules/raw-body/index.js` | ! |
| `paperclip-plugin/node_modules/zod/src/v3/helpers/util.ts` | System module for util.ts. |
| `paperclip-plugin/node_modules/zod/v4/classic/errors.d.ts` | System module for errors.d.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2018.regexp.d.ts` | !  |
| `paperclip-plugin/node_modules/which/which.js` | System module for which.js. |
| `paperclip-plugin/node_modules/mime-types/mimeScore.js` | 'mime-score' back-ported to CommonJS |
| `paperclip-plugin/node_modules/zod/v4/core/regexes.js` | System module for regexes.js. |
| `paperclip-plugin/node_modules/ipaddr.js/ipaddr.min.js` | System module for ipaddr.min.js. |
| `paperclip-plugin/node_modules/router/lib/layer.js` | ! |
| `paperclip-plugin/node_modules/zod/v4/locales/mk.d.ts` | System module for mk.d.ts. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/validation/const.ts` | System module for const.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2017.full.d.ts` | !  |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/applicator/anyOf.ts` | System module for anyOf.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/locales/zh-TW.ts` | System module for zh-TW.ts. |
| `paperclip-plugin/node_modules/zod/mini/index.d.ts` | System module for index.d.ts. |
| `paperclip-plugin/node_modules/zod/v4/classic/checks.js` | System module for checks.js. |
| `paperclip-plugin/node_modules/zod/v4/core/json-schema-processors.d.ts` | System module for json-schema-processors.d.ts. |
| `paperclip-plugin/node_modules/math-intrinsics/isFinite.js` | System module for isFinite.js. |
| `paperclip-plugin/node_modules/zod/v4/locales/fr-CA.d.ts` | System module for fr-CA.d.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/zh-CN.d.ts` | System module for zh-CN.d.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/ms.d.ts` | System module for ms.d.ts. |
| `paperclip-plugin/node_modules/zod/v4/mini/parse.js` | System module for parse.js. |
| `paperclip-plugin/node_modules/react/cjs/react-jsx-dev-runtime.production.min.js` | @license React |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/dynamic/index.ts` | System module for index.ts. |
| `paperclip-plugin/node_modules/side-channel-weakmap/index.js` | System module for index.js. |
| `paperclip-plugin/node_modules/math-intrinsics/abs.d.ts` | System module for abs.d.ts. |
| `paperclip-plugin/node_modules/bytes/index.js` | ! |
| `paperclip-plugin/node_modules/zod/src/v4/core/zsf.ts` | / |
| `paperclip-plugin/node_modules/eventsource/src/types.ts` | System module for types.ts. |
| `paperclip-plugin/node_modules/ip-address/src/v4/constants.ts` | System module for constants.ts. |
| `paperclip-plugin/node_modules/zod/v4/core/json-schema.js` | System module for json-schema.js. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2022.d.ts` | !  |
| `paperclip-plugin/node_modules/loose-envify/replace.js` | System module for replace.js. |
| `paperclip-plugin/node_modules/es-errors/syntax.js` | System module for syntax.js. |
| `paperclip-plugin/node_modules/call-bind-apply-helpers/actualApply.d.ts` | System module for actualApply.d.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2017.d.ts` | !  |
| `paperclip-plugin/node_modules/zod/v3/locales/en.js` | System module for en.js. |
| `paperclip-plugin/node_modules/inherits/inherits.js` | System module for inherits.js. |
| `paperclip-plugin/node_modules/json-schema-traverse/spec/index.spec.js` | System module for index.spec.js. |
| `paperclip-plugin/node_modules/undici-types/global-origin.d.ts` | System module for global-origin.d.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/locales/pt.ts` | System module for pt.ts. |
| `paperclip-plugin/node_modules/zod/src/v3/helpers/errorUtil.ts` | System module for errorUtil.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/ur.d.ts` | System module for ur.d.ts. |
| `paperclip-plugin/node_modules/ajv/lib/compile/validate/applicability.ts` | System module for applicability.ts. |
| `paperclip-plugin/node_modules/path-key/index.d.ts` | / <reference types="node" /> |
| `paperclip-plugin/node_modules/zod/v4/locales/pl.js` | System module for pl.js. |
| `paperclip-plugin/node_modules/zod/v4/core/doc.js` | System module for doc.js. |
| `paperclip-plugin/node_modules/react/cjs/react-jsx-dev-runtime.profiling.min.js` | @license React |
| `paperclip-plugin/node_modules/react/cjs/react.development.js` | @license React |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/jtd/index.ts` | System module for index.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/de.d.ts` | System module for de.d.ts. |
| `paperclip-plugin/node_modules/zod-to-json-schema/createIndex.ts` | System module for createIndex.ts. |
| `paperclip-plugin/node_modules/ip-address/src/ip-address.ts` | System module for ip-address.ts. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/unevaluated/index.ts` | System module for index.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2015.core.d.ts` | !  |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/validation/limitLength.ts` | System module for limitLength.ts. |
| `paperclip-plugin/node_modules/ajv/lib/compile/resolve.ts` | System module for resolve.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2024.object.d.ts` | !  |
| `paperclip-plugin/node_modules/json-schema-typed/draft_2019_09.js` | @generated |
| `paperclip-plugin/node_modules/zod/v4/locales/bg.d.ts` | System module for bg.d.ts. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/jtd/optionalProperties.ts` | System module for optionalProperties.ts. |
| `paperclip-plugin/node_modules/json-schema-typed/draft_07.js` | @generated |
| `paperclip-plugin/node_modules/ip-address/src/address-error.ts` | System module for address-error.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/locales/ja.ts` | System module for ja.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/locales/el.ts` | System module for el.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/locales/zh-CN.ts` | System module for zh-CN.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/mini/parse.ts` | System module for parse.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/classic/index.ts` | System module for index.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/mk.js` | System module for mk.js. |
| `paperclip-plugin/node_modules/zod/src/v4/core/index.ts` | System module for index.ts. |
| `paperclip-plugin/node_modules/safer-buffer/safer.js` | eslint-disable node/no-deprecated-api |
| `paperclip-plugin/node_modules/math-intrinsics/constants/maxSafeInteger.js` | System module for maxSafeInteger.js. |
| `paperclip-plugin/node_modules/zod/v4/core/checks.js` | import { $ZodType } from "./schemas.js"; |
| `paperclip-plugin/node_modules/zod/v4/classic/iso.js` | System module for iso.js. |
| `paperclip-plugin/node_modules/zod/v4/locales/ja.js` | System module for ja.js. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2019.full.d.ts` | !  |
| `paperclip-plugin/node_modules/zod/v4/locales/vi.d.ts` | System module for vi.d.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/locales/ar.ts` | System module for ar.ts. |
| `paperclip-plugin/node_modules/side-channel-list/index.d.ts` | System module for index.d.ts. |
| `paperclip-plugin/node_modules/shebang-command/index.js` | System module for index.js. |
| `paperclip-plugin/node_modules/zod/src/v4/index.ts` | System module for index.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2020.number.d.ts` | !  |
| `paperclip-plugin/node_modules/zod/src/v4/locales/sv.ts` | System module for sv.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/locales/be.ts` | System module for be.ts. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/jtd/error.ts` | System module for error.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2015.collection.d.ts` | !  |
| `paperclip-plugin/node_modules/is-promise/index.js` | System module for index.js. |
| `paperclip-plugin/node_modules/function-bind/implementation.js` | System module for implementation.js. |
| `.agent/mcp-server/handlers_gov.go` | System module for handlers_gov.go. |
| `.agent/mcp-server/db_ops.go` | System module for db_ops.go. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/format/format.ts` | System module for format.ts. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/dynamic/dynamicRef.ts` | System module for dynamicRef.ts. |
| `paperclip-plugin/node_modules/zod/v3/helpers/enumUtil.js` | System module for enumUtil.js. |
| `paperclip-plugin/node_modules/eventsource/src/errors.ts` | An extended version of the `Event` emitted by the `EventSource` object when an error occurs. |
| `paperclip-plugin/node_modules/fast-uri/types/index.d.ts` | System module for index.d.ts. |
| `paperclip-plugin/node_modules/fast-uri/lib/utils.js` | System module for utils.js. |
| `paperclip-plugin/node_modules/zod/v4/locales/sv.d.ts` | System module for sv.d.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/it.d.ts` | System module for it.d.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/uk.js` | System module for uk.js. |
| `paperclip-plugin/node_modules/zod/v4/locales/lt.js` | System module for lt.js. |
| `paperclip-plugin/node_modules/zod/src/v4/locales/uz.ts` | System module for uz.ts. |
| `paperclip-plugin/node_modules/eventsource-parser/src/errors.ts` | The type of error that occurred. |
| `.agent/mcp-server/db_governance.go` | System module for db_governance.go. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/core/ref.ts` | System module for ref.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/fa.js` | System module for fa.js. |
| `paperclip-plugin/node_modules/zod/src/v4/locales/en.ts` | System module for en.ts. |
| `paperclip-plugin/node_modules/react/index.js` | System module for index.js. |
| `paperclip-plugin/node_modules/fast-deep-equal/index.d.ts` | System module for index.d.ts. |
| `paperclip-plugin/node_modules/react/react.shared-subset.js` | System module for react.shared-subset.js. |
| `paperclip-plugin/node_modules/iconv-lite/encodings/dbcs-codec.js` | System module for dbcs-codec.js. |
| `paperclip-plugin/node_modules/debug/src/index.js` | Detect Electron renderer / nwjs process, which is node, but we should |
| `paperclip-plugin/node_modules/math-intrinsics/constants/maxArrayLength.js` | System module for maxArrayLength.js. |
| `.agent/mcp-server/handlers_knowledge.go` | System module for handlers_knowledge.go. |
| `paperclip-plugin/node_modules/zod/src/v3/benchmarks/string.ts` | System module for string.ts. |
| `paperclip-plugin/node_modules/es-errors/ref.js` | System module for ref.js. |
| `paperclip-plugin/node_modules/zod/src/v3/helpers/parseUtil.ts` | System module for parseUtil.ts. |
| `paperclip-plugin/node_modules/ip-address/src/v6/helpers.ts` | @returns {String} the string with all zeroes contained in a <span> |
| `paperclip-plugin/node_modules/zod/src/v3/benchmarks/realworld.ts` | System module for realworld.ts. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/applicator/not.ts` | System module for not.ts. |
| `paperclip-plugin/node_modules/dunder-proto/get.js` | System module for get.js. |
| `paperclip-plugin/node_modules/safer-buffer/dangerous.js` | eslint-disable node/no-deprecated-api |
| `paperclip-plugin/node_modules/zod/v4/locales/az.js` | System module for az.js. |
| `.agent/mcp-server/handlers_discovery.go` | System module for handlers_discovery.go. |
| `paperclip-plugin/node_modules/ajv/lib/compile/codegen/index.ts` | System module for index.ts. |
| `paperclip-plugin/node_modules/path-key/index.js` | System module for index.js. |
| `paperclip-plugin/node_modules/call-bound/index.js` | System module for index.js. |
| `paperclip-plugin/node_modules/eventsource-parser/stream.js` | included for compatibility with react-native without package exports support |
| `paperclip-plugin/node_modules/zod/index.d.ts` | System module for index.d.ts. |
| `paperclip-plugin/node_modules/math-intrinsics/pow.d.ts` | System module for pow.d.ts. |
| `paperclip-plugin/node_modules/math-intrinsics/min.d.ts` | System module for min.d.ts. |
| `paperclip-plugin/node_modules/express/lib/application.js` | ! |
| `paperclip-plugin/node_modules/cross-spawn/lib/util/resolveCommand.js` | System module for resolveCommand.js. |
| `paperclip-plugin/node_modules/ajv/lib/runtime/re2.ts` | System module for re2.ts. |
| `paperclip-plugin/node_modules/zod/v4/classic/from-json-schema.d.ts` | System module for from-json-schema.d.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/no.js` | System module for no.js. |
| `paperclip-plugin/node_modules/math-intrinsics/isNegativeZero.js` | System module for isNegativeZero.js. |
| `paperclip-plugin/node_modules/ajv/lib/compile/jtd/parse.ts` | System module for parse.ts. |
| `paperclip-plugin/node_modules/dunder-proto/set.js` | System module for set.js. |
| `paperclip-plugin/node_modules/typescript/lib/_typingsInstaller.js` | !  |
| `paperclip-plugin/node_modules/zod/src/v3/benchmarks/index.ts` | System module for index.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/ota.js` | System module for ota.js. |
| `paperclip-plugin/node_modules/iconv-lite/encodings/dbcs-data.js` | System module for dbcs-data.js. |
| `paperclip-plugin/node_modules/zod/v4/core/json-schema.d.ts` | System module for json-schema.d.ts. |
| `paperclip-plugin/node_modules/ajv/lib/compile/names.ts` | System module for names.ts. |
| `paperclip-plugin/node_modules/eventsource-parser/src/stream.ts` | System module for stream.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/locales/fi.ts` | System module for fi.ts. |
| `paperclip-plugin/node_modules/undici-types/mock-interceptor.d.ts` | System module for mock-interceptor.d.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/locales/pl.ts` | System module for pl.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/sl.d.ts` | System module for sl.d.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/mini/external.ts` | System module for external.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2016.intl.d.ts` | !  |
| `paperclip-plugin/node_modules/zod/src/v4/core/to-json-schema.ts` | System module for to-json-schema.ts. |
| `paperclip-plugin/node_modules/zod/v4/classic/iso.d.ts` | System module for iso.d.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/hr.js` | System module for hr.js. |
| `paperclip-plugin/node_modules/typescript/lib/typescript.d.ts` | !  |
| `paperclip-plugin/node_modules/typescript/lib/watchGuard.js` | !  |
| `paperclip-plugin/node_modules/zod/src/v3/standard-schema.ts` | The Standard Schema interface. |
| `paperclip-plugin/node_modules/undici-types/connector.d.ts` | System module for connector.d.ts. |
| `paperclip-plugin/node_modules/zod/v4-mini/index.js` | System module for index.js. |
| `paperclip-plugin/node_modules/ajv/lib/runtime/uri.ts` | System module for uri.ts. |
| `paperclip-plugin/node_modules/es-errors/eval.d.ts` | System module for eval.d.ts. |
| `paperclip-plugin/node_modules/zod/v4/index.js` | System module for index.js. |
| `paperclip-plugin/node_modules/mime-types/index.js` | ! |
| `paperclip-plugin/node_modules/eventsource/src/EventSource.ts` | System module for EventSource.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2015.d.ts` | !  |
| `paperclip-plugin/node_modules/typescript/lib/lib.esnext.promise.d.ts` | !  |
| `paperclip-plugin/node_modules/zod/v4/locales/fr-CA.js` | System module for fr-CA.js. |
| `paperclip-plugin/node_modules/zod/src/v4/locales/ru.ts` | System module for ru.ts. |
| `paperclip-plugin/node_modules/on-finished/index.js` | ! |
| `paperclip-plugin/node_modules/math-intrinsics/isFinite.d.ts` | System module for isFinite.d.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/locales/ka.ts` | System module for ka.ts. |
| `paperclip-plugin/node_modules/zod/v4/core/schemas.js` | System module for schemas.js. |
| `paperclip-plugin/node_modules/object-assign/index.js` | object-assign |
| `paperclip-plugin/node_modules/zod/v4/classic/parse.d.ts` | System module for parse.d.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/be.d.ts` | System module for be.d.ts. |
| `paperclip-plugin/node_modules/zod/v4/core/json-schema-generator.js` | System module for json-schema-generator.js. |
| `paperclip-plugin/node_modules/undici-types/env-http-proxy-agent.d.ts` | System module for env-http-proxy-agent.d.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/ru.js` | System module for ru.js. |
| `paperclip-plugin/node_modules/typescript/lib/tsserver.js` | This file is a shim which defers loading the real module until the compile cache is enabled. |
| `paperclip-plugin/node_modules/undici-types/handlers.d.ts` | System module for handlers.d.ts. |
| `paperclip-plugin/node_modules/math-intrinsics/max.d.ts` | System module for max.d.ts. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/jtd/discriminator.ts` | System module for discriminator.ts. |
| `paperclip-plugin/node_modules/es-define-property/index.js` | System module for index.js. |
| `paperclip-plugin/node_modules/zod/v4/locales/id.d.ts` | System module for id.d.ts. |
| `paperclip-plugin/node_modules/es-errors/ref.d.ts` | System module for ref.d.ts. |
| `paperclip-plugin/node_modules/ajv/lib/types/jtd-schema.ts` | numeric strings |
| `paperclip-plugin/node_modules/typescript/lib/lib.es6.d.ts` | !  |
| `paperclip-plugin/node_modules/typescript/lib/lib.esnext.error.d.ts` | !  |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2022.array.d.ts` | !  |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2016.array.include.d.ts` | !  |
| `paperclip-plugin/node_modules/typescript/lib/lib.dom.iterable.d.ts` | !  |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2022.string.d.ts` | !  |
| `paperclip-plugin/node_modules/forwarded/index.js` | ! |
| `paperclip-plugin/node_modules/get-proto/index.d.ts` | System module for index.d.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/ua.d.ts` | System module for ua.d.ts. |
| `paperclip-plugin/node_modules/iconv-lite/lib/streams.js` | System module for streams.js. |
| `paperclip-plugin/node_modules/zod/v4/core/registries.d.ts` | System module for registries.d.ts. |
| `paperclip-plugin/node_modules/get-intrinsic/index.js` | System module for index.js. |
| `paperclip-plugin/node_modules/call-bind-apply-helpers/reflectApply.js` | System module for reflectApply.js. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2024.promise.d.ts` | !  |
| `paperclip-plugin/node_modules/zod/v4/locales/nl.d.ts` | System module for nl.d.ts. |
| `paperclip-plugin/node_modules/zod/v3/helpers/errorUtil.js` | System module for errorUtil.js. |
| `paperclip-plugin/node_modules/zod/src/v4/locales/it.ts` | System module for it.ts. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/errors.ts` | System module for errors.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/classic/from-json-schema.ts` | System module for from-json-schema.ts. |
| `.agent/mcp-server/maintenance.go` | System module for maintenance.go. |
| `paperclip-plugin/node_modules/cookie/index.js` | ! |
| `paperclip-plugin/node_modules/typescript/lib/lib.esnext.collection.d.ts` | !  |
| `paperclip-plugin/node_modules/zod/src/v4/locales/az.ts` | System module for az.ts. |
| `paperclip-plugin/node_modules/ajv/lib/compile/validate/boolSchema.ts` | System module for boolSchema.ts. |
| `paperclip-plugin/node_modules/ajv/lib/jtd.ts` | System module for jtd.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/locales/id.ts` | System module for id.ts. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/draft2020.ts` | System module for draft2020.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/hy.d.ts` | System module for hy.d.ts. |
| `paperclip-plugin/node_modules/react/cjs/react.shared-subset.development.js` | @license React |
| `paperclip-plugin/node_modules/zod/v4/locales/ko.d.ts` | System module for ko.d.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/locales/mk.ts` | System module for mk.ts. |
| `paperclip-plugin/node_modules/zod/v4/core/errors.js` | System module for errors.js. |
| `paperclip-plugin/node_modules/object-inspect/example/fn.js` | System module for fn.js. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2024.collection.d.ts` | !  |
| `paperclip-plugin/node_modules/zod/v4/locales/bg.js` | System module for bg.js. |
| `paperclip-plugin/node_modules/zod/src/v4/classic/compat.ts` | Zod 3 compat layer |
| `paperclip-plugin/node_modules/zod/src/v4/core/util.ts` | System module for util.ts. |
| `paperclip-plugin/node_modules/undici-types/pool-stats.d.ts` | System module for pool-stats.d.ts. |
| `paperclip-plugin/node_modules/zod/v3/helpers/enumUtil.d.ts` | System module for enumUtil.d.ts. |
| `paperclip-plugin/node_modules/zod/v4/classic/checks.d.ts` | System module for checks.d.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/locales/vi.ts` | System module for vi.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/locales/he.ts` | System module for he.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/uz.d.ts` | System module for uz.d.ts. |
| `paperclip-plugin/node_modules/call-bind-apply-helpers/functionCall.d.ts` | System module for functionCall.d.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.esnext.d.ts` | !  |
| `paperclip-plugin/node_modules/fast-deep-equal/es6/react.js` | System module for react.js. |
| `paperclip-plugin/node_modules/content-disposition/index.js` | ! |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2022.regexp.d.ts` | !  |
| `paperclip-plugin/node_modules/zod/v4/core/json-schema-processors.js` | System module for json-schema-processors.js. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2020.string.d.ts` | !  |
| `paperclip-plugin/node_modules/zod/src/v3/helpers/typeAliases.ts` | System module for typeAliases.ts. |
| `paperclip-plugin/node_modules/zod/v4/mini/checks.js` | System module for checks.js. |
| `paperclip-plugin/node_modules/inherits/inherits_browser.js` | System module for inherits_browser.js. |
| `paperclip-plugin/node_modules/undici-types/content-type.d.ts` | / <reference types="node" /> |
| `paperclip-plugin/node_modules/zod/v4/core/api.d.ts` | System module for api.d.ts. |
| `paperclip-plugin/node_modules/zod/v3/index.d.ts` | System module for index.d.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/locales/hy.ts` | System module for hy.ts. |
| `paperclip-plugin/node_modules/zod/v4/core/parse.d.ts` | System module for parse.d.ts. |
| `paperclip-plugin/node_modules/iconv-lite/encodings/utf7.js` | System module for utf7.js. |
| `paperclip-plugin/node_modules/typescript/lib/tsc.js` | This file is a shim which defers loading the real module until the compile cache is enabled. |
| `paperclip-plugin/node_modules/math-intrinsics/min.js` | System module for min.js. |
| `paperclip-plugin/node_modules/zod/v4/locales/vi.js` | System module for vi.js. |
| `paperclip-plugin/node_modules/zod/v4/core/errors.d.ts` | System module for errors.d.ts. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/discriminator/types.ts` | System module for types.ts. |
| `paperclip-plugin/node_modules/ajv/lib/runtime/timestamp.ts` | System module for timestamp.ts. |
| `.agent/mcp-server/db.go` | System module for db.go. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/code.ts` | System module for code.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/locales/no.ts` | System module for no.ts. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/jtd/type.ts` | System module for type.ts. |
| `paperclip-plugin/node_modules/zod/v3/helpers/partialUtil.js` | System module for partialUtil.js. |
| `paperclip-plugin/node_modules/zod/v3/helpers/partialUtil.d.ts` | System module for partialUtil.d.ts. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/format/index.ts` | System module for index.ts. |
| `paperclip-plugin/node_modules/zod/v4/mini/iso.d.ts` | System module for iso.d.ts. |
| `paperclip-plugin/node_modules/zod/locales/index.js` | System module for index.js. |
| `paperclip-plugin/node_modules/zod/src/v4/locales/th.ts` | System module for th.ts. |
| `paperclip-plugin/node_modules/ajv/lib/refs/json-schema-2019-09/index.ts` | System module for index.ts. |
| `paperclip-plugin/node_modules/undici-types/util.d.ts` | System module for util.d.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/locales/ur.ts` | System module for ur.ts. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/validation/uniqueItems.ts` | System module for uniqueItems.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2021.promise.d.ts` | !  |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2023.collection.d.ts` | !  |
| `paperclip-plugin/node_modules/typescript/lib/lib.webworker.importscripts.d.ts` | !  |
| `paperclip-plugin/node_modules/zod/v4/core/to-json-schema.js` | System module for to-json-schema.js. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/applicator/additionalProperties.ts` | System module for additionalProperties.ts. |
| `paperclip-plugin/node_modules/body-parser/lib/types/urlencoded.js` | ! |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2020.bigint.d.ts` | !  |
| `paperclip-plugin/node_modules/zod/src/v4/locales/ca.ts` | System module for ca.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/locales/is.ts` | System module for is.ts. |
| `paperclip-plugin/node_modules/zod/src/v3/helpers/enumUtil.ts` | System module for enumUtil.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/locales/cs.ts` | System module for cs.ts. |
| `paperclip-plugin/node_modules/get-proto/Reflect.getPrototypeOf.d.ts` | System module for Reflect.getPrototypeOf.d.ts. |
| `paperclip-plugin/node_modules/ip-address/src/ipv4.ts` | eslint-disable no-param-reassign |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2022.object.d.ts` | !  |
| `paperclip-plugin/node_modules/zod/src/v4/locales/de.ts` | System module for de.ts. |
| `paperclip-plugin/node_modules/ajv/lib/runtime/equal.ts` | https:github.com/ajv-validator/ajv/issues/889 |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2018.d.ts` | !  |
| `paperclip-plugin/node_modules/json-schema-traverse/index.js` | System module for index.js. |
| `paperclip-plugin/node_modules/call-bind-apply-helpers/applyBind.d.ts` | System module for applyBind.d.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/ota.d.ts` | System module for ota.d.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/ca.d.ts` | System module for ca.d.ts. |
| `paperclip-plugin/node_modules/react/umd/react.production.min.js` | @license React |
| `paperclip-plugin/node_modules/zod/v4/mini/checks.d.ts` | System module for checks.d.ts. |
| `paperclip-plugin/node_modules/es-errors/index.js` | System module for index.js. |
| `paperclip-plugin/node_modules/zod/v3/errors.d.ts` | System module for errors.d.ts. |
| `paperclip-plugin/node_modules/json-schema-traverse/spec/fixtures/schema.js` | System module for schema.js. |
| `paperclip-plugin/node_modules/shebang-regex/index.d.ts` | Regular expression for matching a [shebang](https://en.wikipedia.org/wiki/Shebang_(Unix)) line. |
| `paperclip-plugin/node_modules/zod/v4/locales/ka.js` | System module for ka.js. |
| `paperclip-plugin/node_modules/zod/v4/classic/external.d.ts` | System module for external.d.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.webworker.d.ts` | !  |
| `paperclip-plugin/node_modules/cors/lib/index.js` | System module for index.js. |
| `paperclip-plugin/node_modules/fresh/index.js` | ! |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/metadata.ts` | System module for metadata.ts. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/applicator/prefixItems.ts` | System module for prefixItems.ts. |
| `paperclip-plugin/node_modules/zod/src/v3/benchmarks/primitives.ts` | System module for primitives.ts. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/applicator/if.ts` | System module for if.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/core/parse.ts` | System module for parse.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/core/errors.ts` | System module for errors.ts. |
| `paperclip-plugin/node_modules/ajv/lib/runtime/parseJson.ts` | System module for parseJson.ts. |
| `paperclip-plugin/node_modules/zod/v4/mini/external.d.ts` | System module for external.d.ts. |
| `paperclip-plugin/node_modules/math-intrinsics/constants/maxValue.js` | System module for maxValue.js. |
| `paperclip-plugin/node_modules/typescript/lib/lib.esnext.intl.d.ts` | !  |
| `paperclip-plugin/node_modules/undici-types/diagnostics-channel.d.ts` | System module for diagnostics-channel.d.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/core/json-schema.ts` | System module for json-schema.ts. |
| `paperclip-plugin/node_modules/side-channel-list/index.js` | System module for index.js. |
| `paperclip-plugin/node_modules/ajv-formats/src/index.ts` | System module for index.ts. |
| `paperclip-plugin/node_modules/zod/v4/core/doc.d.ts` | System module for doc.d.ts. |
| `paperclip-plugin/node_modules/es-errors/range.d.ts` | System module for range.d.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2021.weakref.d.ts` | !  |
| `paperclip-plugin/node_modules/call-bind-apply-helpers/reflectApply.d.ts` | System module for reflectApply.d.ts. |
| `paperclip-plugin/node_modules/undici-types/mock-agent.d.ts` | System module for mock-agent.d.ts. |
| `paperclip-plugin/node_modules/call-bind-apply-helpers/index.d.ts` | System module for index.d.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/en.d.ts` | System module for en.d.ts. |
| `.agent/mcp-server/types.go` | System module for types.go. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/applicator/dependentSchemas.ts` | System module for dependentSchemas.ts. |
| `paperclip-plugin/node_modules/zod/v4/classic/index.d.ts` | System module for index.d.ts. |
| `paperclip-plugin/node_modules/http-errors/index.js` | ! |
| `paperclip-plugin/node_modules/zod/src/v4/locales/index.ts` | System module for index.ts. |
| `paperclip-plugin/node_modules/zod/v4/classic/schemas.js` | System module for schemas.js. |
| `paperclip-plugin/node_modules/zod/v4/locales/ro.js` | System module for ro.js. |
| `paperclip-plugin/node_modules/zod/v4/locales/fi.d.ts` | System module for fi.d.ts. |
| `paperclip-plugin/node_modules/object-inspect/example/inspect.js` | System module for inspect.js. |
| `paperclip-plugin/node_modules/iconv-lite/encodings/sbcs-codec.js` | System module for sbcs-codec.js. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/draft7.ts` | System module for draft7.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/sv.js` | System module for sv.js. |
| `paperclip-plugin/node_modules/undici-types/patch.d.ts` | / <reference types="node" /> |
| `paperclip-plugin/node_modules/typescript/lib/lib.decorators.legacy.d.ts` | !  |
| `paperclip-plugin/node_modules/zod/src/v4/locales/lt.ts` | System module for lt.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/it.js` | System module for it.js. |
| `paperclip-plugin/node_modules/call-bind-apply-helpers/applyBind.js` | System module for applyBind.js. |
| `paperclip-plugin/node_modules/ajv-formats/src/formats.ts` | System module for formats.ts. |
| `paperclip-plugin/node_modules/ajv/lib/compile/rules.ts` | System module for rules.ts. |
| `paperclip-plugin/node_modules/es-object-atoms/isObject.js` | System module for isObject.js. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2018.full.d.ts` | !  |
| `paperclip-plugin/node_modules/zod/v4/locales/ua.js` | System module for ua.js. |
| `paperclip-plugin/node_modules/zod/v4/locales/ur.js` | System module for ur.js. |
| `paperclip-plugin/node_modules/zod/src/v4/core/json-schema-generator.ts` | System module for json-schema-generator.ts. |
| `paperclip-plugin/node_modules/call-bind-apply-helpers/functionApply.d.ts` | System module for functionApply.d.ts. |
| `paperclip-plugin/node_modules/zod/v4/core/checks.d.ts` | System module for checks.d.ts. |
| `paperclip-plugin/node_modules/qs/lib/utils.js` | System module for utils.js. |
| `paperclip-plugin/node_modules/zod/src/v4/core/schemas.ts` | System module for schemas.ts. |
| `paperclip-plugin/node_modules/math-intrinsics/abs.js` | System module for abs.js. |
| `paperclip-plugin/node_modules/express/lib/utils.js` | ! |
| `paperclip-plugin/node_modules/zod/v4/classic/coerce.js` | System module for coerce.js. |
| `paperclip-plugin/node_modules/typescript/lib/typescript.js` | !  |
| `paperclip-plugin/node_modules/require-from-string/index.js` | System module for index.js. |
| `.agent/mcp-server/handlers_infra.go` | System module for handlers_infra.go. |
| `paperclip-plugin/node_modules/ajv/lib/vocabularies/applicator/additionalItems.ts` | System module for additionalItems.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2015.generator.d.ts` | !  |
| `paperclip-plugin/node_modules/zod/v4/locales/fr.js` | System module for fr.js. |
| `paperclip-plugin/node_modules/zod/v4/mini/index.d.ts` | System module for index.d.ts. |
| `paperclip-plugin/node_modules/depd/index.js` | ! |
| `paperclip-plugin/node_modules/iconv-lite/lib/bom-handling.js` | System module for bom-handling.js. |
| `paperclip-plugin/node_modules/zod/src/v4/locales/sl.ts` | System module for sl.ts. |
| `paperclip-plugin/node_modules/zod/v4/classic/coerce.d.ts` | System module for coerce.d.ts. |
| `paperclip-plugin/node_modules/zod/v4/core/index.js` | System module for index.js. |
| `paperclip-plugin/node_modules/ajv/lib/compile/codegen/code.ts` | eslint-disable-next-line @typescript-eslint/no-extraneous-class |
| `paperclip-plugin/node_modules/zod/v4/locales/kh.js` | System module for kh.js. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2019.object.d.ts` | !  |
| `paperclip-plugin/node_modules/has-symbols/index.d.ts` | System module for index.d.ts. |
| `paperclip-plugin/node_modules/cross-spawn/lib/util/escape.js` | System module for escape.js. |
| `paperclip-plugin/node_modules/media-typer/index.js` | ! |
| `paperclip-plugin/node_modules/zod/src/mini/index.ts` | System module for index.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/is.d.ts` | System module for is.d.ts. |
| `paperclip-plugin/node_modules/eventsource-parser/src/index.ts` | System module for index.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2020.symbol.wellknown.d.ts` | !  |
| `paperclip-plugin/node_modules/undici-types/api.d.ts` | System module for api.d.ts. |
| `paperclip-plugin/node_modules/zod/v4/locales/ro.d.ts` | System module for ro.d.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/core/regexes.ts` | System module for regexes.ts. |
| `paperclip-plugin/node_modules/zod/src/v4/locales/fa.ts` | System module for fa.ts. |
| `paperclip-plugin/node_modules/zod/v4/core/standard-schema.d.ts` | The Standard interface. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2020.sharedmemory.d.ts` | !  |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2018.promise.d.ts` | !  |
| `paperclip-plugin/node_modules/ajv/lib/compile/index.ts` | System module for index.ts. |
| `paperclip-plugin/node_modules/ajv/lib/compile/validate/keyword.ts` | System module for keyword.ts. |
| `paperclip-plugin/node_modules/express/lib/request.js` | ! |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2024.full.d.ts` | !  |
| `paperclip-plugin/node_modules/zod/src/v4-mini/index.ts` | System module for index.ts. |
| `paperclip-plugin/node_modules/typescript/lib/_tsc.js` | !  |
| `paperclip-plugin/node_modules/zod/v4/locales/km.js` | System module for km.js. |
| `paperclip-plugin/node_modules/loose-envify/cli.js` | System module for cli.js. |
| `paperclip-plugin/node_modules/zod/v4/index.d.ts` | System module for index.d.ts. |
| `.agent/mcp-server/db_security.go` | System module for db_security.go. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2017.date.d.ts` | !  |
| `paperclip-plugin/node_modules/undici-types/index.d.ts` | System module for index.d.ts. |
| `paperclip-plugin/node_modules/typescript/lib/lib.es2018.asynciterable.d.ts` | !  |
