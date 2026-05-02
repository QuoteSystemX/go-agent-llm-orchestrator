---
description: BMAD Phase 1. Runs Socratic interview with user and produces wiki/BRIEF.md. Entry point for the BMAD product lifecycle. Use before /prd, /architecture-bmad, /stories, /sprint.
---

# /discovery — BMAD Discovery Phase

$ARGUMENTS

---

## Purpose

Produce `wiki/BRIEF.md` through a structured Socratic interview. No code. No PRD yet. Discovery and brief only.

## Step 0: Total Gateway Audit (Phases 18-21)
- Run `ambiguity_detector.py`, `intent_validator.py`, `impact_analyzer.py`, `threat_modeler.py`, `failure_correlator.py`, `discovery_brain_sync.py`, `context_autofill.py`, `ghost_prototyper.py`.
- **Mandatory**: Report all findings (conflicts, blast radius, security, history, prototype) before starting.

---

## Pre-Flight

Check if `wiki/BRIEF.md` already exists:
- If **exists** → read it and ask: "A brief already exists. Do you want to (A) update it or (B) start fresh?"
- If **missing** → proceed to interview.

---

## Execution

Use the `analyst` agent to run Phase 1: Discovery.

Provide this context:

```
MODE: DISCOVERY (Phase 1 of BMAD)
GOAL: Produce wiki/BRIEF.md
INPUT: $ARGUMENTS (use as initial idea if provided, otherwise start from scratch)

RULES:
1. Run Phase 1 from analyst.md
2. Ask minimum 5 Socratic questions before drafting anything
3. Write wiki/BRIEF.md only after user provides answers
4. STOP after wiki/BRIEF.md is approved — do NOT proceed to PRD
5. Final confirmation: "[BRIEF APPROVED — run /prd to continue]"
```

---

## Approval Gate

After `wiki/BRIEF.md` is drafted, present it in full and ask:

```
wiki/BRIEF.md is ready. Here's the summary:
[show brief]

✅ Approve this brief?
- Y / yes: Brief locked. Run /prd to continue to Phase 2.
- N / no: Tell me what to change and I'll revise.
```

Do NOT proceed to Phase 2 without explicit approval.

---

## Output

| Deliverable | Location |
|-------------|----------|
| Discovery Brief | `wiki/BRIEF.md` |

---

## Usage

```
/discovery
/discovery we want to build a real-time notification service
/discovery the idea is to add WebSocket support for live price updates
```
