# Knowledge Anchors

`redirect` and `context` intents **require** a `knowledge_anchor` —
a reference to a section in `KNOWLEDGE.md` (or the kit's knowledge
base). This ensures the agent always has grounded context for the
message, not just floating instructions.

## What is a knowledge anchor?

A string of the form:
- `#section-name` (hash + lowercase-with-hyphens)
- `Section-Name` (Title-Case-With-Hyphens, will be normalized)
- `path/to/section#subsection`

The validator (regex in the schema) accepts:
```python
ANCHOR_PATTERN = re.compile(r"^#?[A-Za-z0-9_-]+(#[A-Za-z0-9_-]+)?$")
```

So `mypath#mysection` is also valid (path + section).

## Why anchors?

Without anchors, `redirect` is just a free-form instruction:
```yaml
# BAD
intent: redirect
body: "use pgx"
```

The agent has no way to know **why** or what policy supports this.
It might disagree and ignore.

With an anchor, the agent reads the section first:
```yaml
# GOOD
intent: redirect
body: "use pgx instead of database/sql"
knowledge_anchor: "#postgres-policy"
```

Now the agent reads `#postgres-policy` in `KNOWLEDGE.md`, sees "we
use pgx for PostgreSQL", and applies the redirect with context.

## Naming conventions

- Lowercase-with-hyphens: `#postgres-policy`, `#abort-policy`
- Dots allowed in path-style: `#auth.password-hashing`
- Underscores allowed: `#test_patterns`
- Numbers allowed: `#error-404-handling`

Avoid:
- Spaces (use hyphens)
- Special chars: `*`, `?`, `/`, `\`, `..`
- Very long names (>50 chars)

## What goes in the anchored section?

The section should:
- **State the rule/policy clearly** (not just "see ADR-007")
- **Give rationale** (why this is the policy)
- **Provide examples** (so the agent knows what to do)

Example `KNOWLEDGE.md` section:
```markdown
## #postgres-policy

We use `pgx` for all PostgreSQL connections in this project.

**Rationale:** pgx is faster, more idiomatic, and supports the
PostgreSQL-specific features we use (LISTEN/NOTIFY, COPY protocol).

**Examples:**
- Use `pgxpool.Pool` for connection pooling
- Use `pgx.NamedArgs` for parameterized queries
- NEVER use `database/sql` + `lib/pq` (legacy)

See ADR-007 (broker-native daemon) for the broader connection
management context.
```

Now when the agent reads `body: "use pgx"` + `anchor: "#postgres-policy"`,
it has:
- The rule: use pgx
- The rationale: faster, supports LISTEN/NOTIFY
- The implementation: pgxpool, NamedArgs
- What NOT to do: lib/pq

That's much better than just "use pgx" floating in space.

## Where to put sections

Sections can live in:
- `.agent/KNOWLEDGE.md` — primary knowledge base
- `wiki/decisions/ADR-NNN-*.md` — specific ADRs
- `wiki/fragments/core/*.md` — focused topics

For best discoverability, put operational policies in
`.agent/KNOWLEDGE.md` (so the daemon's knowledge_inject picks them up).

## Where anchors are validated

The schema regex check is at:
- `bin/inbox send` — validates at write time
- `.agent/scripts/communication/inbox.py::validate_entry` — programmatic API
- `tasks/INBOX_viewer.html` — visual indication in browser

If the anchor doesn't match the regex, the message is rejected at write.
You don't get a "soft" warning.

## Examples

```bash
# Reference an ADR
bin/inbox send context "follow the security audit process" --anchor "#ADR-007-process"

# Reference a code section (rare, but useful for very specific rules)
bin/inbox send redirect "the bug is in src/api/v2/auth.py" --anchor "#auth.py:42"

# Reference a process section
bin/inbox send context "follow the testing protocol" --anchor "#test-protocol"
```

## Anti-patterns

### ❌ Anchor without a real section
```bash
# BAD — anchor doesn't exist anywhere
bin/inbox send redirect "use pgx" --anchor "#postgres-policy"
# If KNOWLEDGE.md doesn't have a "#postgres-policy" section, the
# agent can't find it. Use a section that exists, or write the section first.
```

### ❌ Vague anchor
```bash
# BAD — anchor is too generic to be useful
bin/inbox send context "follow our standards" --anchor "#standards"
# Agent has no idea which standards you mean.
```

Better: specific anchor like `#coding-standards` or
`#test-coverage-requirements`.

### ❌ Anchor in body, not in field
```bash
# BAD — anchor is in the body, not in the dedicated field
bin/inbox send redirect "see #postgres-policy for the policy" --anchor ""
# Schema rejects this (anchor required for redirect).
```

Better: always put the anchor in the field, not the body.
