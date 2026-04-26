---
name: wiki-writing
description: Karpathy Wiki-First methodology — Mental Model documents, Intuition sections, Prose-First specification, wiki vs code drift detection, and evergreen knowledge architecture. Universal — works in Antigravity (Gemini) and Claude Code.
version: 1.0.0
---

# Wiki-Writing Skill (Karpathy Method)

The primary source of truth for any system is its **wiki** — not the code, not the comments, not the PR descriptions. This skill teaches how to write wiki documents that transfer deep understanding, not just facts.

> "If you can't explain it simply, you don't understand it well enough." — Feynman
> "The wiki is the specification. The code is the implementation." — Karpathy method

---

## 🧠 THE KARPATHY WIKI-FIRST PRINCIPLE

### What it means

**Wiki-First** means: before a single line of code is written for a new component, a **Mental Model** document MUST exist in `wiki/`. The document answers three questions:

1. **WHY does this exist?** — The problem it solves, the alternatives rejected.
2. **HOW does it work conceptually?** — The mental model, intuition, analogies.
3. **WHAT are the invariants?** — The rules that must never be broken.

Code implements the wiki. If they diverge — the wiki is right until proven otherwise.

### Source of Truth Priority

```
wiki/ (intended behavior)
  ↓ if code is demonstrably more correct/recent
code/ (actual behavior)
  ↓ resolution: update wiki immediately, never leave drift
wiki/ (back in sync)
```

### What wiki is NOT

| ❌ Not wiki | ✅ Wiki |
|------------|---------|
| Auto-generated API docs | Mental model of why the API is shaped this way |
| Inline code comments | Invariants and constraints that cannot be derived from reading code |
| README installation steps | Architecture decisions and the reasoning behind them |
| Changelog | Evergreen knowledge that remains true across versions |
| PR description | The lasting "why we built it this way" |

---

## 📐 DOCUMENT TYPES & TEMPLATES

### 1. Mental Model Document (most important)

Use for: any system component, subsystem, algorithm, or architectural pattern.

```markdown
# [Component Name] — Mental Model

## Intuition

[2-4 paragraphs. Explain the concept as you would to a smart person who has
never seen this codebase. Use analogies. Explain the "gestalt" — why the
pieces fit together the way they do. Include the mathematical or logical
foundation if relevant.]

## Why This Exists

[What problem does this solve? What would break or be harder without it?
What alternatives were considered and why were they rejected?]

## Core Invariants

[Bullet list of rules that must ALWAYS be true. These are the things that,
if violated, indicate a bug or a misuse of the component.]

- Invariant 1: ...
- Invariant 2: ...

## The Mental Picture

[Optional ASCII diagram, state machine, or data flow that makes the structure
immediately obvious. Prefer ASCII over external diagrams — it stays in sync.]

## Common Misconceptions

[What do people usually get wrong when first encountering this? What traps
exist? This section prevents repeating past debugging sessions.]

## References

[Links to relevant code files, external papers, or related wiki pages.]
```

### 2. Architecture Decision Record (ADR)

Use for: every non-obvious technical decision.

```markdown
# ADR-NNN: [Decision Title]

**Status**: Accepted | Deprecated | Superseded by ADR-NNN
**Date**: YYYY-MM-DD

## Context

[What situation forced this decision? What constraints existed?]

## Decision

[What was decided, stated clearly.]

## Consequences

**Positive:**
- ...

**Negative (accepted trade-offs):**
- ...

## Alternatives Considered

| Option | Why Rejected |
|--------|-------------|
| ...    | ...         |
```

### 3. System Design Document

Use for: major features, cross-cutting concerns, data pipelines.

```markdown
# [Feature/System] — Design

## Problem Statement

[One paragraph. What user problem or technical need is being addressed?]

## Intuition

[The "aha" explanation. Why is the design shaped this way? What analogy
makes it click? What is the core insight that drove the design?]

## Architecture

[ASCII diagram of the main components and their relationships.]

## Data Flow

[Step-by-step trace of the most important operation through the system.]

## Failure Modes

[What can go wrong? How does the system degrade gracefully?]

## Open Questions

[Things not yet decided. Date them — stale open questions are noise.]
```

### 4. Algorithm Explainer

Use for: non-trivial algorithms, data structures, concurrency patterns.

```markdown
# [Algorithm Name]

## Intuition

[Explain in plain language what the algorithm does and WHY it works.
The intuition section is the most important — if a reader understands
the intuition, they can re-derive the implementation.]

## Mathematical Foundation

[The formal definition, recurrence, or invariant that makes it correct.
Even one equation that captures the essence is valuable.]

## Step-by-Step Example

[Trace through a concrete small example. Use tables or ASCII art.]

## Complexity

| | Time | Space |
|-|------|-------|
| Best | ... | ... |
| Average | ... | ... |
| Worst | ... | ... |

## Edge Cases

[The inputs that break naive implementations.]
```

---

## ✍️ WRITING THE INTUITION SECTION

The Intuition section is the hardest and most valuable part of any wiki document. Rules:

### Rule 1: Explain WHY before WHAT

```
❌ "The cache uses an LRU eviction policy."
✅ "We use LRU because cache hits on recently-used data are far more likely
   than on old data (temporal locality). LRU is the simplest policy that
   captures this — it evicts the item we're least likely to need."
```

### Rule 2: Use the right analogy

A good analogy makes the concept stick in 10 seconds. Test it: can a junior engineer who has never touched this code understand the component from the analogy alone?

```
❌ "The event loop processes events from a queue."
✅ "The event loop is like a restaurant expediter: it sits at the pass,
   takes finished dishes (completed I/O), and routes them to the right
   waiter (callback). The kitchen (OS) does the slow work; the expediter
   just coordinates. This is why Node.js can handle thousands of concurrent
   requests on a single thread — it never blocks waiting for the kitchen."
```

### Rule 3: State the Gestalt

The Gestalt is the "reason the pieces are shaped the way they are." It's the answer to "why does this design make sense as a whole?"

```
The Gestalt of an event loop: async I/O lets the CPU stay busy instead of
waiting. All the other properties (single-threaded, callback-based, non-blocking)
follow from this one insight.
```

### Rule 4: Include the mathematical invariant when relevant

Not every component needs an equation, but when the correctness depends on a formal property, state it:

```
The correctness of this merge algorithm rests on one invariant:
  at the start of each iteration, result[0..i] contains the i smallest
  elements from both arrays in sorted order.
If this invariant holds at i=0 (trivially) and is preserved by each step,
then at i=n it holds for the full result.
```

---

## 🔍 WIKI vs CODE DRIFT DETECTION

Drift = wiki describes behavior X, code implements behavior Y.

### Detection Protocol

```bash
# 1. For each wiki page, find the corresponding code files
#    (wiki/cache.md → pkg/cache/*.go)

# 2. Check for structural drift: do the sections in wiki match what exists?
grep -r "func \|type \|class " pkg/cache/ | grep -v test

# 3. Check for behavioral drift: do invariants still hold?
#    Run tests that correspond to wiki invariants

# 4. Check for staleness: when was wiki last updated vs code?
git log --oneline wiki/cache.md | head -1
git log --oneline pkg/cache/ | head -1
```

### Drift Severity

| Level | Example | Action |
|-------|---------|--------|
| **Critical** | Wiki says X is atomic; code is not | Fix immediately, block PR |
| **Major** | New feature added to code, not documented in wiki | Write wiki section before merging |
| **Minor** | API signature changed, wiki shows old signature | Update wiki in same PR |
| **Cosmetic** | Wiki uses old naming convention | Update in next doc pass |

### The "Conflict Resolution" Rule

When wiki and code disagree:
1. Ask: "Is the code change intentional and correct?"
2. If YES → update wiki to match the new reality
3. If UNSURE → treat wiki as spec, investigate code
4. **Never leave the conflict unresolved**

---

## 📁 WIKI DIRECTORY STRUCTURE

```
wiki/
├── BRIEF.md              # BMAD Phase 1 — product brief
├── PRD.md                # BMAD Phase 2 — product requirements
├── ARCHITECTURE.md       # BMAD Phase 3 — architecture decisions
├── DECISIONS.md          # ADR index
├── GOTCHAS.md            # Codebase pitfalls (hard-won knowledge)
├── sprints/              # BMAD sprint boards
│   └── sprint-NN.md
├── mental-models/        # Component Mental Models (Karpathy)
│   ├── auth-system.md
│   ├── event-loop.md
│   └── cache-layer.md
├── algorithms/           # Algorithm explainers
│   └── consensus.md
└── adrs/                 # Architecture Decision Records
    ├── 001-database-choice.md
    └── 002-auth-strategy.md
```

---

## ✅ WIKI QUALITY CHECKLIST

Before considering a wiki document complete:

- [ ] **Intuition section exists** and uses at least one analogy
- [ ] **WHY is answered** — not just what it does, but why it was built this way
- [ ] **Core invariants listed** — the rules that make it correct
- [ ] **Common misconceptions covered** — saves future debugging sessions
- [ ] **Prose-first**: was this written before or alongside the code? (not after)
- [ ] **No staleness markers** — no "TODO: update this section"
- [ ] **No implementation leakage** — wiki describes concepts, not `if` statements
- [ ] **Drift check passed** — wiki matches current code behavior

---

## 🔄 KEEPING WIKI ALIVE (EVERGREEN PROTOCOL)

A wiki that isn't maintained becomes worse than no wiki — it actively misleads.

### Evergreen Rules

1. **Every code PR that changes behavior** must include a wiki update in the same PR
2. **Every ADR** must be written at decision time, not reconstructed later
3. **The `GOTCHAS.md`** grows with every non-obvious debugging session: "we lost 3 hours to X, here's why it happens and how to fix it"
4. **Monthly drift scan**: run `wiki-architect` agent monthly to check all `mental-models/` against code

### The One-Line Test

For any wiki page, a reader should be able to answer:
> "What would I need to know to confidently modify this component?"

If the page doesn't answer that, it's incomplete.

---

## Changelog

- **1.0.0** (2026-04-26): Initial version — Karpathy Wiki-First methodology, Mental Model templates, Intuition writing rules, drift detection, evergreen protocol

<!-- EMBED_END -->
