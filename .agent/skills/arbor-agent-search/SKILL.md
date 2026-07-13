---
name: arbor-agent-search
description: "Related-work and novelty annotation phase for Arbor. Use after a node has been experimentally validated, especially before merge decisions, to emulate SearchIdeaContext/SearchIdeaContextParallel/SearchStatus, validated-node gating, background SearchAgent behavior, and structured prior-art summaries."
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
version: 1.0
priority: NORMAL
---
# Arbor Search Agent

Use this for post-experiment related-work annotation. It is not for internal
codebase search; use normal file tools for that.

## Eligibility Gate

By default, only search nodes that are validated and effective:

- node status is `done` or `merged`;
- node has a numeric score;
- score improves over current `trunk_score`, or over `baseline_score` if trunk
  is unavailable.

Skip pending, running, unscored, and below-trunk nodes. This keeps novelty cost
tied to merge candidates.

## When To Search

- After `RunExecutor` returns a node with `score > trunk_score`.
- Before `GitMergeBranch` when novelty or related work affects the decision.
- After parallel executor results, annotate all sibling winners with
  `SearchIdeaContextParallel`.

Do not search trivial parameter tweaks, pure scale-ups, or internal codebase
questions.

## SearchAgent Task

The SearchAgent is a novelty scout. It does not implement, critique, or change
the idea. It surveys prior work and writes a Markdown annotation to
`node.related_work`.

Use 2-3 query angles:

- technique class;
- application domain;
- key mechanism.

For ML/NLP literature, use English academic queries with words such as
`paper`, `arxiv`, or `survey`; include one original-language query when useful.

## Instructions

1. **Verify eligibility first** — check the node's status, score, and
   comparison to trunk/baseline. Skip nodes that don't pass the gate.
2. **Run SearchAgent in background** — search is async, so don't
   block the main merge decision on it.
3. **Read the annotation** when SearchAgent finishes, and decide
   whether to merge, defer, or reject based on novelty + related
   work.
4. **Use `SearchIdeaContextParallel`** for sibling winners from a
   parallel run, so each gets its own search annotation.
5. **Don't merge a node without an annotation** if it improves over
   trunk — the annotation is the audit trail.

### How to run a search

```bash
# Via the SearchAgent MCP tool (preferred)
search_idea_context(
    node_id="...",
    status="done",
    include_papers=True,
    include_implementations=True
)
```

The agent returns a JSON envelope with `summary`, `related_papers`,
`related_implementations`, and `novelty` fields.

## Anti-Patterns

- **Don't search trivial parameter tweaks** — they're noise, not
  novelty. The search agent should focus on algorithmic or
  architectural changes.
- **Don't skip the eligibility gate** — searching pending or
  below-trunk nodes wastes tokens and dilutes the search pool.
- **Don't merge on incomplete search** — if SearchAgent is still
  running, defer the merge decision.
- **Don't use this skill for internal codebase search** — use
  `Grep`, `Glob`, or `Read` tools instead. This skill is for
  external prior-art.
- **Don't trust SearchAgent output blindly** — it's a survey, not
  a verdict. A human reviewer must still sign off.

## Hard Caps

- At most 2 search rounds.
- Visit up to 5 pages total.
- Keep the result short enough for a researcher to judge novelty quickly.

## Final JSON Schema

When running an isolated SearchAgent, ask it to emit only:

```json
{
  "summary": "2-4 sentences describing prior work.",
  "related_papers": [
    {
      "title": "Paper title",
      "url": "https://...",
      "one_line_relevance": "Why this is relevant."
    }
  ],
  "novelty_assessment": "novel | partial-overlap | prior-art-exists",
  "overlap_risks": "What specifically overlaps, or 'none'."
}
```

Render it into:

```text
### Summary
...

### Related Papers
- [Title](url) - relevance

### Novelty
novel | partial-overlap | prior-art-exists - justification

### Overlap Risks
...
```

## Background Behavior

Native Arbor usually runs SearchAgent in the background:

- `SearchIdeaContext` returns a dispatch message immediately.
- The coordinator continues IDEATE/DISPATCH work.
- The result lands on `node.related_work` later.
- `SearchStatus` reports in-flight searches.
- Shutdown waits for pending searches to flush.

When emulating in a host that lacks background tasks, run search synchronously
and update `related_work` before merging.

## Failure Handling

Failures are non-blocking. Write a marker such as:

```text
[search-failed: <reason>]
```

Treat it as no information, not evidence of novelty.
