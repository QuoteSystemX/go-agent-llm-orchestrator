---
description: BMAD Phase 3. Reads wiki/PRD.md and produces wiki/ARCHITECTURE.md with ADRs, component map, data flow, and security considerations. Run after /prd.
---

# /architecture-bmad — BMAD Architecture Phase

$ARGUMENTS

---

## Purpose

Produce `wiki/ARCHITECTURE.md` from the approved PRD. Document system components, technology decisions as ADRs, data flow, and security considerations.

---

## Pre-Condition Checks

```
IF wiki/PRD.md does NOT exist:
  → STOP
  → Tell user: "wiki/PRD.md not found. Run /prd first."

IF wiki/PRD.md has no approval marker:
  → Warn: "PRD does not show approval. Proceed anyway? (Y/N)"
  → Wait for response before continuing.

IF wiki/ARCHITECTURE.md already exists:
  → Read it and ask: "Architecture doc already exists.
    Do you want to (A) update/extend it or (B) start fresh?"
```

---

## Execution

Use the `analyst` agent to run Phase 3: Architecture.

Provide this context:

```
MODE: ARCHITECTURE (Phase 3 of BMAD)
INPUT: wiki/PRD.md
OUTPUT: wiki/ARCHITECTURE.md
TEMPLATE: .agent/wiki-templates/ARCHITECTURE.md
SKILLS: architecture, bmad-lifecycle
ADDITIONAL FOCUS: $ARGUMENTS (e.g. "focus on security decisions", "emphasize scalability ADRs")

RULES:
1. Read wiki/PRD.md fully before writing
2. Use architecture skill for ADR format
3. Identify components for every epic in the PRD
4. Write one ADR per major technology decision
5. Map data flow for the primary user story paths
6. List security considerations per component
7. List open questions with owner assignments
8. Write wiki/ARCHITECTURE.md using the template structure
9. Present to user for approval before exiting
10. STOP after approval — do NOT generate story cards yet
```

---

## Approval Gate

```
wiki/ARCHITECTURE.md is ready.
[N] components, [M] ADRs, [K] open questions.

✅ Approve this architecture?
- Y / yes: Architecture locked. Run /stories to generate task cards.
- N / no: Which section or ADR needs revision?
```

---

## Output

| Deliverable | Location |
|-------------|----------|
| Architecture Document | `wiki/ARCHITECTURE.md` |

---

## Usage

```
/architecture-bmad
/architecture-bmad focus on security decisions and threat model
/architecture-bmad we're using Go with gRPC for the backend
```
