---
description: BMAD Phase 2. Reads wiki/BRIEF.md and produces wiki/PRD.md with full user stories, Gherkin AC, and MoSCoW priorities. Run after /discovery.
---

# /prd — BMAD PRD Phase

$ARGUMENTS

---

## Purpose

Convert the approved `wiki/BRIEF.md` into a full Product Requirements Document at `wiki/PRD.md`.

---

## Pre-Condition Check

```
IF wiki/BRIEF.md does NOT exist:
  → STOP
  → Tell user: "wiki/BRIEF.md not found. Run /discovery first to create the brief."
  → Do NOT proceed.

IF wiki/PRD.md already exists:
  → Read it and ask: "PRD already exists (check approval status).
    Do you want to (A) update it or (B) start fresh?"
```

---

## Execution

Use the `analyst` agent to run Phase 2: PRD.

Provide this context:

```
MODE: PRD (Phase 2 of BMAD)
INPUT: wiki/BRIEF.md
OUTPUT: wiki/PRD.md
TEMPLATE: .agent/wiki-templates/PRD.md
ADDITIONAL FOCUS: $ARGUMENTS (e.g. "MVP only", "focus on security stories")

RULES:
1. Read wiki/BRIEF.md completely before writing anything
2. Expand each persona into 2–5 user stories
3. Write Gherkin AC (Given/When/Then) for every story
4. Apply MoSCoW prioritization to all stories
5. Write wiki/PRD.md using the template structure exactly
6. Present to user for approval before exiting
7. STOP after approval — do NOT proceed to Architecture
```

---

## Approval Gate

```
wiki/PRD.md is ready.
[N] user stories across [M] epics.
MUST: [count], SHOULD: [count], COULD: [count], WON'T: [count]

✅ Approve this PRD?
- Y / yes: PRD locked. Run /architecture-bmad to continue to Phase 3.
- N / no: Tell me which section or story needs revision.
```

---

## Output

| Deliverable | Location |
|-------------|----------|
| Product Requirements Document | `wiki/PRD.md` |

---

## Usage

```
/prd
/prd focus on MVP only — ignore COULD and WON'T stories for now
/prd add more detail to the authentication epic
```
