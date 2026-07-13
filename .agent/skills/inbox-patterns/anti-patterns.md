# INBOX Anti-Patterns

Common mistakes when using the INBOX channel. Each shows the wrong
way and the right way.

## Anti-pattern 1: Markdown in body

**Wrong:**
```bash
bin/inbox send clarify "look at **users** table; use `LEFT JOIN` for nullable fields"
```

**Why it's wrong:** Bold, code, and other formatting is stripped by
`strip_for_prompt()`. The agent sees:
```
look at users table; use LEFT JOIN for nullable fields
```

**Right:**
```bash
bin/inbox send clarify "look at users table; use LEFT JOIN for nullable fields"
```

Plain text survives intact. Don't rely on formatting.

## Anti-pattern 2: Code blocks

**Wrong:**
```bash
bin/inbox send context "use this pattern:
\`\`\`
pgxpool.New(ctx, "postgres://...")
\`\`\`" --anchor "#postgres"
```

**Why it's wrong:** Backticks are stripped. The agent sees the code
with no formatting, harder to read.

**Right:** Either:
- Put the code pattern in the `KNOWLEDGE.md` anchor section (so it
  gets formatted properly there), and just refer to it:
  ```bash
  bin/inbox send context "use the pgx pool init pattern from #postgres" --anchor "#postgres"
  ```
- Or describe in plain English:
  ```bash
  bin/inbox send context "for pgx pool init: pass context, then DSN string" --anchor "#postgres"
  ```

## Anti-pattern 3: Missing anchor on `redirect`/`context`

**Wrong:**
```bash
bin/inbox send redirect "use pgx"
```

**Why it's wrong:** The schema REJECTS this. The CLI returns:
```
❌ Validation failed: Invalid inbox entry: intent=redirect requires knowledge_anchor
```

**Right:**
```bash
bin/inbox send redirect "use pgx" --anchor "#postgres-policy"
```

If the anchor doesn't exist, write the section in `KNOWLEDGE.md` first.

## Anti-pattern 4: Anchor that doesn't exist

**Wrong:**
```bash
bin/inbox send redirect "use pgx" --anchor "#postgres"  # section not in KNOWLEDGE.md
```

**Why it's wrong:** The schema accepts the anchor (it matches the
regex), but the agent looks for the section and can't find it. The
message is dropped from the agent's context.

**Right:** Either:
- Use an existing anchor: `bin/inbox send redirect "use pgx" --anchor "#postgres-policy"`
- Or add the section to `KNOWLEDGE.md` first, then use the new anchor.

To check if an anchor exists:
```bash
grep -n "^#\+ .*postgres" .agent/KNOWLEDGE.md
```

## Anti-pattern 5: Body >2000 chars

**Wrong:**
```bash
bin/inbox send clarify "$(cat long-instructions.md)"  # 3000 chars
```

**Why it's wrong:** The schema truncates to 2000 chars. The agent
gets only the first 2000 chars, possibly missing critical context.

**Right:** Break the message into multiple INBOX entries, or move
the long content into a `KNOWLEDGE.md` section and reference it.

## Anti-pattern 6: Forgetting to ack

**Wrong:**
```bash
# Send message
bin/inbox send redirect "use pgx" --anchor "#postgres"
# ... time passes, agent applies the redirect ...
# ... but the entry stays "unacked", keeps being injected in next tasks ...
```

**Why it's wrong:** The daemon reads `include_acked=False`, so unacked
entries keep being injected. This pollutes the prompt with old context.

**Right:**
```bash
# After the agent has applied the redirect
bin/inbox ack inb_20260711_120000_abcdef
```

The entry moves to "acked" state and won't be re-injected.

## Anti-pattern 7: Markdown tables in body

**Wrong:**
```bash
bin/inbox send context "use this table:
| Cap | Role | Scope |
| modify-bus | infra | global |
" --anchor "#caps"
```

**Why it's wrong:** `|` is preserved but formatting is gone. The
agent sees a wall of text. Also, this is hard to read in a console.

**Right:** Put the table in `KNOWLEDGE.md#caps` and reference it.

## Anti-pattern 8: Targeting by task_id when task is done

**Wrong:**
```bash
bin/inbox send context "remember to use pgx" --target task_abc
# ... but task_abc is already completed ...
# ... the new task doesn't see the INBOX because target doesn't match ...
```

**Why it's wrong:** The `--target` filter only shows entries for the
matching task. If the task is done and a new one starts, the entry is
filtered out.

**Right:**
- Omit `--target` (the entry is shown to any task)
- Or use a `scope` style (e.g., `target: ""` for global)
- Or use a section name in the anchor that applies to all tasks

## Anti-pattern 9: Conflicting intents in one entry

**Wrong:**
```bash
# Body has both redirect AND abort in it
bin/inbox send redirect "use pgx" --body "and also abort if you can't" --anchor "#postgres"
```

**Why it's wrong:** The intent is `redirect`, so the agent will try
to redirect. The "abort" in the body is buried in plain text and
might be missed.

**Right:** Send two separate entries:
```bash
bin/inbox send redirect "use pgx" --anchor "#postgres"
bin/inbox send abort "if pgx fails, stop and notify" --anchor "#abort-policy"
```

## Anti-pattern 10: Using `ack` as a reply

**Wrong:**
```bash
# Agent responds with explanation; user acks
bin/inbox send ack "thanks for the explanation, I now understand"
```

**Why it's wrong:** `ack` is for the agent's INBOX (acknowledging
human messages). For human → agent, use `clarify` or `context`.

**Right:**
```bash
bin/inbox send context "explanation noted, no further questions" --anchor "#ack-policy"
```

## Anti-pattern 11: Sensitive data in INBOX

**Wrong:**
```bash
bin/inbox send clarify "my API key is sk-1234567890abcdef"
```

**Why it's wrong:** INBOX is logged to bus, persisted to disk, and
shown in the HTML viewer. Sensitive data should not go here.

**Right:** Use environment variables or secrets manager, and tell the
agent which variable to use:
```bash
bin/inbox send clarify "use the OPENAI_API_KEY env var (set in .env)" --anchor "#api-keys"
```
