# INBOX Intents

The 5 intents in INBOX.md v2 are the **verb** of the message. Choosing
the right intent is critical — it tells the agent what to do.

## Quick reference

| Intent | When to use | Requires anchor? | Effect on agent |
|--------|-------------|------------------|-----------------|
| `redirect` | Change the agent's course | YES (required) | Stops current path, follows the redirect |
| `clarify` | Ask for more info | no | Agent responds with the requested info |
| `abort` | Stop the agent entirely | YES (required) | Stops the task, logs the reason |
| `context` | Add knowledge reference | YES (required) | Adds info to the agent's working context |
| `ack` | Acknowledge a previous response | no | Just marks the previous entry as handled |

## `redirect` — Change the agent's course

**Use when**: The agent is going in the wrong direction and you want
to redirect it.

**Examples:**
```bash
# Wrong model: switch to pgx
bin/inbox send redirect "use pgx instead of database/sql" --anchor "#postgres"

# Wrong approach: use a different strategy
bin/inbox send redirect "use BFS not DFS for graph traversal" --anchor "#graph-algorithms"

# Wrong file: target a different file
bin/inbox send redirect "modify the v2 version in src/api_v2.py, not src/api.py" --anchor "#api-versioning"
```

**Anchored to**: A `KNOWLEDGE.md` section that explains why the new
approach is better.

## `clarify` — Ask for more info

**Use when**: The agent is missing context and you need to provide it
or ask a question.

**Examples:**
```bash
# Question about schema
bin/inbox send clarify "what is the schema of the users table?"

# Ask for explanation
bin/inbox send clarify "explain why you chose option B over option A"

# Request more detail
bin/inbox send clarify "can you give me the exact line numbers for the bug?"
```

**No anchor required** — `clarify` is just a question.

**Tip**: If the agent is supposed to find an answer itself, don't use
`clarify` — let it work. Use `clarify` when the info is external
(you have it, the agent doesn't).

## `abort` — Stop the agent

**Use when**: The agent is going in a fundamentally wrong direction
and you want to stop it entirely (not redirect).

**Examples:**
```bash
# Wrong task entirely
bin/inbox send abort "this is the wrong feature, cancel and wait for new spec" --target task_abc --anchor "#abort-policy"

# Runaway execution
bin/inbox send abort "the loop is infinite, stop now" --target task_xyz --anchor "#abort-policy"

# Architectural disagreement
bin/inbox send abort "this approach violates our security policy, stop" --anchor "#security-policy"
```

**Anchored to**: An `abort-policy` section (typically in `KNOWLEDGE.md`)
that explains when abort is appropriate.

**Difference from `redirect`**: `redirect` says "do this instead",
`abort` says "stop and wait".

## `context` — Add knowledge reference

**Use when**: The agent is missing context that you can provide via
a KNOWLEDGE.md reference.

**Examples:**
```bash
# Point to relevant section
bin/inbox send context "see the auth section for the policy" --anchor "#auth-policy"

# Reference an ADR
bin/inbox send context "ADR-007 explains the daemon lifecycle" --anchor "#daemon-lifecycle"

# Cross-reference
bin/inbox send context "the test pattern is in #test-patterns" --anchor "#test-patterns"
```

**Anchored to**: A `KNOWLEDGE.md` section. The agent will read this
section as part of its context.

**Tip**: Use `context` for **references**, not for new information.
If you need to convey new info that isn't in KNOWLEDGE.md, use
`clarify` and provide the info in the body.

## `ack` — Acknowledge a previous response

**Use when**: You (or the agent) want to mark a previous entry as
handled without further action.

**Examples:**
```bash
# After the agent responded to your clarify
bin/inbox send ack "thanks, got it"

# Mark a context message as read
bin/inbox send ack "context noted, no action needed"
```

**No anchor required** — `ack` is just a marker.

**Tip**: Always ack entries the agent acted on, so the daemon doesn't
keep injecting them in future tasks.

## Anti-patterns

### ❌ `redirect` without anchor
```bash
# BAD — will be rejected
bin/inbox send redirect "use pgx"
# Error: intent=redirect requires knowledge_anchor
```

### ❌ Using `context` for new info
```bash
# BAD — body is plain text only
bin/inbox send context "I want you to use bcrypt for passwords" --anchor "#auth"
# The agent will look up #auth but won't find "bcrypt" — info is lost
```

Better: write the info into `KNOWLEDGE.md#auth`, then send the redirect.

### ❌ Markdown in body
```bash
# BAD — markdown is sanitized away
bin/inbox send clarify "look at **users** table; use `LEFT JOIN`"
# Result: "look at users table; use LEFT JOIN" (bold and code stripped)
```

Better: plain text, no formatting.

## Decision tree

```
Want to communicate with a running agent.
│
├─ Want to change its course?
│  ├─ Have a specific alternative → redirect (anchor required)
│  └─ Want it to stop and wait → abort (anchor required)
│
├─ Need info it doesn't have?
│  ├─ Info is in KNOWLEDGE.md → context (anchor required)
│  ├─ Info is external (you have it) → clarify + put info in body
│  └─ Info needs a question → clarify
│
└─ Just acknowledging?
   └─ ack
```
