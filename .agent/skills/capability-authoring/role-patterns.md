# Role Patterns

The kit defines 4 standard roles. New roles should follow these
patterns unless there's strong justification otherwise.

## Standard roles

### `infra-agent` (highest trust)
**Purpose**: Daemon, maintenance scripts, infrastructure tools.

**Typical capabilities:**
- `modify-bus`, `read-bus` — full bus access
- `execute-cli-low`, `execute-cli-high` — can run any CLI
- `modify-infra`, `read-infra` — can touch `.agent/`
- `start-daemon`, `stop-daemon` — lifecycle ops
- `trigger-distill` — knowledge loop
- `modify-tasks`, `read-tasks` — story cards
- `modify-config` — capabilities.yaml, harnesses.yaml
- `harness-run` — can invoke any registered harness

**Constraint**: sensitive caps get `constraint` field documented.

**Example:**
```yaml
infra-agent:
  capabilities:
    - { cap: modify-bus,    scope: global }
    - { cap: execute-cli-high, scope: global, constraint: "no_shell_injection" }
    - { cap: harness-run,   scope: global, constraint: "manifest_required" }
```

### `squad-agent` (orchestrator level)
**Purpose**: Squad orchestrator, multi-agent coordination.

**Typical capabilities:**
- `modify-bus`, `read-bus` — bus access (limited)
- `read-infra` — read infrastructure
- `trigger-distill` — can trigger knowledge loop
- `modify-tasks` (scoped to `task:*`) — manage tasks
- `read-tasks` — read all tasks
- `harness-run` — can invoke harnesses (with constraint)

**No** `modify-infra`, `modify-config`, `start-daemon` — those are
infra-agent only.

**Example:**
```yaml
squad-agent:
  capabilities:
    - { cap: read-bus,      scope: global }
    - { cap: trigger-distill, scope: global }
    - { cap: modify-tasks,  scope: "task:*" }
    - { cap: harness-run,   scope: global, constraint: "manifest_required" }
```

### `session-agent` (default-deny, ephemeral)
**Purpose**: Individual specialist agents (49 of them).

**Typical capabilities:**
- **NONE.** The capabilities list is empty `[]`.

This is the **default-deny invariant**. session-agents should request
capability elevation per-task via the orchestrator, not have standing
capabilities.

**Example:**
```yaml
session-agent:
  capabilities: []    # ⚠️  DO NOT add anything here
```

If a session-agent needs to do something privileged, it should:
1. Submit a request to the orchestrator
2. Orchestrator (with `squad-agent` or `infra-agent` role) executes on
   its behalf
3. Result is returned to the session-agent

### `human` (operator)
**Purpose**: Manual operator commands, read-mostly.

**Typical capabilities:**
- `read-bus` — see what's happening
- `read-infra` — see configuration
- `read-tasks` — see stories
- `modify-tasks` — mark stories as done
- `stop-daemon` — emergency stop
- `trigger-distill` — force distillation

**No** `modify-infra`, `modify-config`, `execute-cli-high` —
humans are trusted but slow; delegation is preferred.

**Example:**
```yaml
human:
  capabilities:
    - { cap: read-bus,     scope: global }
    - { cap: modify-tasks, scope: global }
    - { cap: stop-daemon,  scope: global }
```

## Adding a new role

If you need a new role (e.g., `monitor-agent`, `release-agent`):

1. **Write an ADR first** in `wiki/decisions/`. Justify why the
   existing 4 roles don't fit.
2. **Start with empty capabilities** `[]`. Add only what's needed.
3. **Add audit check** if it has unusual caps (e.g., `monitor-agent`
   might have `read-*` but no `write-*`).
4. **Run `capability_audit.py`** — must pass.
5. **Update this skill** with the new role's pattern.

## Role comparison table

| Capability | infra | squad | session | human |
|------------|-------|-------|---------|-------|
| modify-bus | ✅ | ✅ | ❌ | ❌ |
| read-bus | ✅ | ✅ | ❌ | ✅ |
| execute-cli-low | ✅ | ❌ | ❌ | ❌ |
| execute-cli-high | ✅ | ❌ | ❌ | ❌ |
| modify-infra | ✅ | ❌ | ❌ | ❌ |
| read-infra | ✅ | ✅ | ❌ | ✅ |
| start-daemon | ✅ | ❌ | ❌ | ❌ |
| stop-daemon | ✅ | ❌ | ❌ | ✅ |
| trigger-distill | ✅ | ✅ | ❌ | ✅ |
| modify-tasks | ✅ | ✅ (task:*) | ❌ | ✅ |
| read-tasks | ✅ | ✅ | ❌ | ✅ |
| modify-config | ✅ | ❌ | ❌ | ❌ |
| harness-run | ✅ | ✅ (constraint) | ❌ | ❌ |

This table is the **principle of least privilege** in action. Use it
when designing new roles or granting new caps.
