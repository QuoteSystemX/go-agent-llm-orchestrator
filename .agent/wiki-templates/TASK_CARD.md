<!--
Canonical ad-hoc task-queue card template. Covers [BUG] [SECURITY] [PERF] [TEST] [REFACTOR]
[DOCS] [CHORE] [INFRA] — the tags reviewer.md's audit and autonomous_reviewer_cron.py actually
produce. NOT for [STORY] [EPIC] [PRD] [ARCHITECTURE] [DECISIONS] — those are BMAD-lifecycle
artifacts (see .agent/workflows/stories.md) with their own templates in this same directory
(STORY.md, EPIC.md, ...). Rendered by render_task_card() in .agent/scripts/lib/common.py, which
strips this comment block before formatting — it never appears in an actual generated card.

Field guidance:
  tag                  One of the ad-hoc tags above, no brackets — the template adds them.
  title                Short and specific — describes the actual problem, not the category.
  agent                Primary agent expected to pick this up (see KNOWLEDGE.md Pickup Matrix).
  priority             Critical / High / Medium / Low.
  source               How this was found (e.g. "autonomous_reviewer_cron", "code-review", a
                        person/agent name, or a sibling ticket reference).
  problem               What was found and why it matters. Inline evidence (file:line, code
                        snippets) here rather than in a separate Evidence section.
  acceptance_criteria   Markdown checklist, specific and testable — not vague.
  context               Anything else the executing agent needs that doesn't fit above.

Closing convention — not part of the initial render; appended by hand, or by
drift_detector.py::close_resolved_cards() for auto-closed drift cards, when the card is actually
closed, before it moves into tasks/done/:

  ## Resolution [YYYY-MM-DD]
  **Status**: CLOSED
  **Closed by**: <agent name, or the mechanism that closed it>

  Free-text: what shipped / was found, what was verified, what was deliberately deferred.
-->
# [{tag}] {title}

**Date**: {date}
**Agent**: `{agent}`
**Priority**: {priority}
**Source**: {source}

## Problem

{problem}

## Acceptance Criteria

{acceptance_criteria}

## Context

{context}
