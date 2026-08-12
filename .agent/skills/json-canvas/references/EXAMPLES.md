# JSON Canvas: Complete Examples

Four full `.canvas` files exercising every node type, edge options, and colors documented in
`SKILL.md`. Each is valid, complete JSON — copy the fenced block into a `.canvas` file as-is.

---

## 1. Mind Map

A central topic radiating into branches, with one sub-node one level deeper. Uses undirected
edges (`toEnd: "none"`) since mind-map branches aren't a flow of causality.

```json
{
  "nodes": [
    { "id": "c1a2b3c4d5e6f701", "type": "text", "x": 600, "y": 400, "width": 220, "height": 100, "text": "# 🎙 Launch a Podcast" },
    { "id": "c1a2b3c4d5e6f702", "type": "text", "x": 200, "y": 150, "width": 200, "height": 90, "text": "## Content\n- Episode topics\n- Guest pipeline", "color": "2" },
    { "id": "c1a2b3c4d5e6f703", "type": "text", "x": 1000, "y": 150, "width": 200, "height": 90, "text": "## Production\n- Recording setup\n- Editing workflow", "color": "5" },
    { "id": "c1a2b3c4d5e6f704", "type": "text", "x": 200, "y": 650, "width": 200, "height": 90, "text": "## Distribution\n- Spotify\n- Apple Podcasts\n- RSS feed", "color": "4" },
    { "id": "c1a2b3c4d5e6f705", "type": "text", "x": 1000, "y": 650, "width": 200, "height": 90, "text": "## Marketing\n- Social clips\n- Newsletter", "color": "1" },
    { "id": "c1a2b3c4d5e6f706", "type": "text", "x": 200, "y": 0, "width": 180, "height": 70, "text": "Episode 1: Intro & Mission" }
  ],
  "edges": [
    { "id": "e1a2b3c4d5e6f701", "fromNode": "c1a2b3c4d5e6f701", "fromSide": "left", "toNode": "c1a2b3c4d5e6f702", "toSide": "right", "toEnd": "none" },
    { "id": "e1a2b3c4d5e6f702", "fromNode": "c1a2b3c4d5e6f701", "fromSide": "right", "toNode": "c1a2b3c4d5e6f703", "toSide": "left", "toEnd": "none" },
    { "id": "e1a2b3c4d5e6f703", "fromNode": "c1a2b3c4d5e6f701", "fromSide": "left", "toNode": "c1a2b3c4d5e6f704", "toSide": "right", "toEnd": "none" },
    { "id": "e1a2b3c4d5e6f704", "fromNode": "c1a2b3c4d5e6f701", "fromSide": "right", "toNode": "c1a2b3c4d5e6f705", "toSide": "left", "toEnd": "none" },
    { "id": "e1a2b3c4d5e6f705", "fromNode": "c1a2b3c4d5e6f702", "fromSide": "top", "toNode": "c1a2b3c4d5e6f706", "toSide": "bottom", "toEnd": "arrow", "label": "first" }
  ]
}
```

---

## 2. Project Board (Kanban)

Three `group` nodes as columns, with `text` nodes as cards positioned inside each group's bounds.
Kanban boards typically need no edges — card-to-column membership is purely geometric (a card's
`x`/`y`/`width`/`height` falls inside its column group's bounds), so `edges` is empty here.

```json
{
  "nodes": [
    { "id": "b1a2b3c4d5e6f701", "type": "group", "x": 0, "y": 0, "width": 300, "height": 500, "label": "To Do", "color": "1" },
    { "id": "b1a2b3c4d5e6f702", "type": "text", "x": 20, "y": 60, "width": 260, "height": 80, "text": "Design onboarding flow" },
    { "id": "b1a2b3c4d5e6f703", "type": "text", "x": 20, "y": 160, "width": 260, "height": 80, "text": "Write API docs" },

    { "id": "b1a2b3c4d5e6f704", "type": "group", "x": 350, "y": 0, "width": 300, "height": 500, "label": "In Progress", "color": "3" },
    { "id": "b1a2b3c4d5e6f705", "type": "text", "x": 370, "y": 60, "width": 260, "height": 80, "text": "Implement auth flow" },
    { "id": "b1a2b3c4d5e6f706", "type": "text", "x": 370, "y": 160, "width": 260, "height": 80, "text": "Set up CI pipeline" },

    { "id": "b1a2b3c4d5e6f707", "type": "group", "x": 700, "y": 0, "width": 300, "height": 500, "label": "Done", "color": "4" },
    { "id": "b1a2b3c4d5e6f708", "type": "text", "x": 720, "y": 60, "width": 260, "height": 80, "text": "Project kickoff" }
  ],
  "edges": []
}
```

---

## 3. Research Canvas

Mixes all three data-bearing node types (`text`, `link`, `file`) to show a hypothesis supported by
cited sources, with labeled edges tracing the evidence chain.

```json
{
  "nodes": [
    { "id": "r1a2b3c4d5e6f701", "type": "text", "x": 400, "y": 0, "width": 400, "height": 120, "text": "# Hypothesis\nUsers churn because onboarding takes >10 minutes." },
    { "id": "r1a2b3c4d5e6f702", "type": "link", "x": 0, "y": 250, "width": 350, "height": 150, "url": "https://example.com/onboarding-benchmark-report" },
    { "id": "r1a2b3c4d5e6f703", "type": "file", "x": 400, "y": 250, "width": 350, "height": 150, "file": "Research/user-interviews-2026-06.pdf" },
    { "id": "r1a2b3c4d5e6f704", "type": "text", "x": 800, "y": 250, "width": 400, "height": 180, "text": "## Findings\n- Avg onboarding time: 14 min\n- 62% drop-off before step 3" },
    { "id": "r1a2b3c4d5e6f705", "type": "text", "x": 400, "y": 500, "width": 400, "height": 120, "text": "# Conclusion\nShorten onboarding to <5 min; re-test in Q3." }
  ],
  "edges": [
    { "id": "re1a2b3c4d5e6f701", "fromNode": "r1a2b3c4d5e6f702", "toNode": "r1a2b3c4d5e6f704", "toEnd": "arrow", "label": "cited by" },
    { "id": "re1a2b3c4d5e6f702", "fromNode": "r1a2b3c4d5e6f703", "toNode": "r1a2b3c4d5e6f704", "toEnd": "arrow", "label": "cited by" },
    { "id": "re1a2b3c4d5e6f703", "fromNode": "r1a2b3c4d5e6f704", "toNode": "r1a2b3c4d5e6f701", "toEnd": "arrow", "label": "supports" },
    { "id": "re1a2b3c4d5e6f704", "fromNode": "r1a2b3c4d5e6f704", "toNode": "r1a2b3c4d5e6f705", "toEnd": "arrow", "label": "leads to" }
  ]
}
```

---

## 4. Flowchart

A linear process with a branch, using labeled directional edges (`"Yes"` / `"No"`) for the
decision point — the standard way to represent branching logic in JSON Canvas, since there is no
dedicated "diamond/decision" node type in the spec.

```json
{
  "nodes": [
    { "id": "f1a2b3c4d5e6f701", "type": "text", "x": 400, "y": 0, "width": 200, "height": 80, "text": "**Start**: Push to main" },
    { "id": "f1a2b3c4d5e6f702", "type": "text", "x": 400, "y": 150, "width": 200, "height": 80, "text": "Run CI tests" },
    { "id": "f1a2b3c4d5e6f703", "type": "text", "x": 400, "y": 300, "width": 200, "height": 100, "text": "**Tests pass?**" },
    { "id": "f1a2b3c4d5e6f704", "type": "text", "x": 200, "y": 470, "width": 200, "height": 80, "text": "Deploy to production", "color": "4" },
    { "id": "f1a2b3c4d5e6f705", "type": "text", "x": 600, "y": 470, "width": 200, "height": 80, "text": "Notify author, block merge", "color": "1" },
    { "id": "f1a2b3c4d5e6f706", "type": "text", "x": 400, "y": 620, "width": 200, "height": 80, "text": "**End**" }
  ],
  "edges": [
    { "id": "fe1a2b3c4d5e6f701", "fromNode": "f1a2b3c4d5e6f701", "toNode": "f1a2b3c4d5e6f702", "toEnd": "arrow" },
    { "id": "fe1a2b3c4d5e6f702", "fromNode": "f1a2b3c4d5e6f702", "toNode": "f1a2b3c4d5e6f703", "toEnd": "arrow" },
    { "id": "fe1a2b3c4d5e6f703", "fromNode": "f1a2b3c4d5e6f703", "toNode": "f1a2b3c4d5e6f704", "toEnd": "arrow", "label": "Yes" },
    { "id": "fe1a2b3c4d5e6f704", "fromNode": "f1a2b3c4d5e6f703", "toNode": "f1a2b3c4d5e6f705", "toEnd": "arrow", "label": "No" },
    { "id": "fe1a2b3c4d5e6f705", "fromNode": "f1a2b3c4d5e6f704", "toNode": "f1a2b3c4d5e6f706", "toEnd": "arrow" },
    { "id": "fe1a2b3c4d5e6f706", "fromNode": "f1a2b3c4d5e6f705", "toNode": "f1a2b3c4d5e6f706", "toEnd": "arrow" }
  ]
}
```
