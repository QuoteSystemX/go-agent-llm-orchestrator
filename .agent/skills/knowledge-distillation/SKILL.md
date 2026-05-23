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
