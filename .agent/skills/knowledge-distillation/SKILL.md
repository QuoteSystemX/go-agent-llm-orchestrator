---
name: knowledge-distillation
description: "Distilling operational logs, incident post-mortems, and debugging runs into evergreen lessons."
version: 1.0.0
---

# Knowledge Distillation Skill (Master Level)

This skill defines the procedures and mandatory rules for distilling high-entropy operational logs, incident post-mortems, and debugging runs into evergreen structural lessons.

---

## 🎯 Primary Goal
Maximize cognitive efficiency. Prevent token bloat by extracting reusable patterns and compressing chat transcripts into lightweight context snapshots.

---

## 🧠 Distilled Lesson Entry Standards

Every time a bug is fixed, a performance bottleneck is solved, or an architectural discovery is made, it **MUST** be recorded in `.agent/rules/LESSONS_LEARNED.md` or indexed via the experience distiller.

### Approved Lesson Schema:
```markdown
### [YYYY-MM-DD] [TYPE] [skill-domain] Title

**Context:**
Brief description of the environment, dependencies, and what was being built.

**Failure Mode:**
Why did it break? Show the specific error trace or code anti-pattern.

**Remediation:**
How was it fixed? Provide a code diff or terminal command.

**Invariant:**
The golden rule to prevent this from happening again.
```

### Concrete Example of a Real Lesson:
```markdown
### [2026-05-12] [BUG] [go-patterns] xsync MapOf Nil Pointer Initialization

**Context:**
Initializing concurrent cache for the quote validation worker using the `xsync` library.

**Failure Mode:**
We initialized the map using standard struct declaration:
```go
type WorkerCache struct {
    validators xsync.MapOf[string, *Validator]
}
// validatorCache.validators.Store("key", val) -> Panic: Nil pointer dereference
```
`xsync.MapOf` contains unexported pointer fields and does not support nil struct instantiation.

**Remediation:**
Always initialize the concurrent map using `xsync.NewMapOf[K, V]()`:
```go
cache := &WorkerCache{
    validators: *xsync.NewMapOf[string, *Validator](),
}
```

**Invariant:**
Never declare `xsync.MapOf` as a bare struct variable. Always use `NewMapOf` constructor.
```

---

## ⚡ Context Snapshot & Bus Serialization

When chat history or context memory grows too large (slowing down reasoning or hitting context limits), you **MUST** distill the state.

### How to Serialize a Context Snapshot:
1. **Analyze active work**: Identify completed tasks, active tasks, and blockers.
2. **Compile snapshot DTO**: Structure the active state as a JSON payload.
3. **Save to Context Bus**: Write the payload to `.agent/bus/snapshots/`.

#### Example Snapshot JSON:
```json
{
  "snapshot_id": "snap_20260523_api_auth",
  "timestamp": "2026-05-23T21:15:00Z",
  "active_goal": "Integrate Lucia auth with Neon Postgres",
  "completed_tasks": [
    "tasks/TASK-001_db_migration.md",
    "tasks/TASK-002_drizzle_schemas.md"
  ],
  "active_task": "tasks/TASK-003_session_middleware.md",
  "blockers": [],
  "critical_invariants": [
    "Lucia sessions must be stored in database table 'user_sessions'",
    "Tokens must be invalidated on explicit client logouts"
  ]
}
```
*Action:* Instruct the next agent or sub-agent: *"Context has been distilled. Pull state snapshot `snap_20260523_api_auth` from the Context Bus to resume."*


## When to Use

- **After a long agent session** — capture the lessons
  before context is lost.
- **After a post-mortem** — turn root causes into lessons.
- **After a successful feature** — capture what worked, so the
  next agent doesn't rediscover it.
- **Periodic audit** — `archivist_trigger.py` runs the distillation
  pipeline automatically.

Avoid using this skill for:
- One-off debugging (use `@debugger`).
- One-line fixes (no distillation needed).
- Documentation (use `@documentation-writer`).

## Anti-Patterns

- **Don't write generic lessons** — "be careful with X" is
  useless. Be specific: "When calling Y with Z>10, set W first
  because V fails silently."
- **Don't skip the format** — use the standard
  `### [date] [tag] [skill] title` format so the lesson is
  findable.
- **Don't write lessons that won't apply elsewhere** — if it's
  a one-off bug, write a test, not a lesson.
- **Don't ignore the TTL** — `applied_count=0` after 30 days =
  prune. Stale lessons pollute search.
- **Don't conflate lessons with code** — lessons are knowledge,
  code is implementation. Update the code; don't just write a
  lesson about the bug.
- **Don't write lessons without verifying** — only distill
  after the lesson has been confirmed (code merged, postmortem
  signed off, etc.).