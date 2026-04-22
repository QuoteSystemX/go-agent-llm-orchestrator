---
name: bmad-lifecycle
description: BMAD product lifecycle phase knowledge. Phases: Discovery → PRD → Architecture → Stories → Sprint. Each phase produces a wiki artifact consumed by the next. Use when driving structured product development, interpreting BMAD artifacts, or routing story cards to specialist agents.
allowed-tools: Read, Glob, Grep
---

# BMAD Lifecycle Framework

## Phase Map

| Phase        | Slash Command         | Input                          | Output                          | Owner Agent    |
|--------------|-----------------------|--------------------------------|---------------------------------|----------------|
| Discovery    | `/discovery`          | User idea / brief              | `wiki/BRIEF.md`                 | analyst        |
| PRD          | `/prd`                | `wiki/BRIEF.md`                | `wiki/PRD.md`                   | analyst        |
| Architecture | `/architecture-bmad`  | `wiki/PRD.md`                  | `wiki/ARCHITECTURE.md`          | analyst        |
| Stories      | `/stories`            | PRD + ARCHITECTURE             | `tasks/[STORY]-*.md` (batch)    | analyst        |
| Sprint       | `/sprint`             | backlog tasks                  | `wiki/sprints/sprint-NN.md`     | analyst        |
| Execution    | automatic (Jules)     | sprint board + task cards      | PR per story                    | specialist agents |

## Phase Completion Gates

Each phase MUST receive explicit user approval before the next begins.

| Gate                  | Signal                                    |
|-----------------------|-------------------------------------------|
| Brief → PRD           | User approves `wiki/BRIEF.md`             |
| PRD → Architecture    | User approves `wiki/PRD.md`               |
| Architecture → Stories| User approves `wiki/ARCHITECTURE.md`      |
| Stories → Sprint      | User selects tasks from backlog           |
| Sprint → Execution    | Sprint board frozen, Jules picks up tasks |

## Artifact Contracts

### BRIEF.md (Discovery Output)
Required sections: Problem Statement, Target Users, Success Metrics, Constraints, Out of Scope.

### PRD.md (PRD Output)
Required sections: Objective, User Personas, User Stories (with Gherkin AC), MoSCoW Priority, Milestones, Risks, Approval block.

### ARCHITECTURE.md (Architecture Output)
Required sections: System Context, Components, Data Flow, ADRs, Security Considerations, Open Questions, Approval block.

### Sprint Board (`wiki/sprints/sprint-NN.md`)
Required sections: Sprint Goal, Selected Tasks (links to task card filenames), Capacity, Definition of Done.

## BMAD Task Tags

| Tag       | Meaning                     | Routing                                              |
|-----------|-----------------------------|------------------------------------------------------|
| `[EPIC]`  | Multi-story grouping card   | `analyst` — tracking only, not directly executable   |
| `[STORY]` | Single user story card      | Treat identically to `[FEAT]` — routed to `backend-specialist`, `frontend-specialist`, or `orchestrator` |

## Story Card Format (MANDATORY)

All `[STORY]` task cards MUST use this exact format — identical to `[FEAT]` cards from `reviewer.md`:

```markdown
> [!IMPORTANT]
> !SILENT execution: No dialogue allowed. ZERO-TEXT finalization required.

# [STORY] Story Title

## Context
Epic: [epic name]. PRD Section: [N]. Persona: [user persona name].
[Background: why this story is needed now.]

## Impact
[Business metric this unlocks. Severity if skipped: Low / Medium / High / Critical.]

## Fix Hint / Implementation Guide
- Target files: `path/to/file.ext`
- API contract: `POST /endpoint → {field: type}` (if applicable)
- Patterns to follow: [reference KNOWLEDGE.md section or ARCHITECTURE.md ADR]
- Edge cases to handle: [list]

## Acceptance Criteria
- [ ] Given [context] When [action] Then [outcome]
- [ ] Given [context] When [action] Then [outcome]
- [ ] Unit tests written and passing
- [ ] No regression in related module
```

## Phase Routing (for analyst agent)

When the analyst receives any BMAD request, it MUST first determine the current phase:

```
IF wiki/BRIEF.md missing         → Run Discovery (Phase 1)
IF wiki/PRD.md missing           → Run PRD (Phase 2)
IF wiki/ARCHITECTURE.md missing  → Run Architecture (Phase 3)
IF tasks/ has no [STORY] cards   → Run Stories (Phase 4)
IF wiki/sprints/ has no active sprint → Run Sprint (Phase 5)
ELSE                             → Report current phase status
```

## Wiki Integration

BMAD artifacts are placed directly into the target repository's `wiki/` directory alongside the existing knowledge graph:

```
wiki/
├── _index.md           ← updated to include BMAD artifact links
├── BRIEF.md            ← Discovery output
├── PRD.md              ← PRD output
├── ARCHITECTURE.md     ← Architecture output
├── DECISIONS.md        ← ADR log (populated by knowledge_updater)
├── GOTCHAS.md          ← Codebase pitfalls (populated by knowledge_updater)
└── sprints/
    └── sprint-NN.md    ← Sprint boards
```

Templates for all BMAD artifacts are in `.agent/wiki-templates/` and distributed to all target repos via `distribute-agentic-kit.yml`.
