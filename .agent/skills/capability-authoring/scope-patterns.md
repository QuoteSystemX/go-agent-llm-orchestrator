# Scope Patterns

Capabilities in `.agent/config/capabilities.yaml` have a `scope` field
that restricts where the cap applies. The four scope types are
described here.

## Scope types

### `global`
**Meaning**: Applies everywhere.

**Use case**: The cap should work on any repo, any task, any context.

**Example:**
```yaml
- { cap: read-bus, scope: global }
- { cap: modify-tasks, scope: global }
```

### `repo:NAME`
**Meaning**: Applies only in the named repo.

**Use case**: Multi-repo deployments where a cap should be limited to
a specific project.

**Example:**
```yaml
- { cap: modify-infra, scope: "repo:prompt-library" }
- { cap: modify-config, scope: "repo:prompt-library" }
```

Currently the kit operates in a single repo (the `prompt-library` itself),
so `repo:*` scopes are rare. They exist for forward-compatibility.

### `task:ID`
**Meaning**: Applies only to a specific task.

**Use case**: Time-bound, task-specific capability (e.g., "this agent
can modify only THIS task's files").

**Example:**
```yaml
- { cap: modify-tasks, scope: "task:abc123" }
```

Currently not heavily used, but planned for fine-grained per-task
permissions.

### `task:*` (wildcard)
**Meaning**: Applies to ANY task.

**Use case**: An agent that manages the task queue but not specific
tasks.

**Example:**
```yaml
- { cap: modify-tasks, scope: "task:*" }
```

This is what `squad-agent` has — it can manage any task in the queue.

## Scope matching algorithm

The `capability_check.check()` function matches scopes like this:

```python
def _scope_matches(cap_scope, target_scope):
    if cap_scope == "global":
        return True                        # global covers everything
    if cap_scope == target_scope:
        return True                        # exact match
    if cap_scope.endswith(":*"):
        prefix = cap_scope[:-1]            # "task:"
        return target_scope.startswith(prefix)  # "task:abc".startswith("task:")
    return False
```

So:
- `global` matches any target scope
- `task:abc` matches `task:abc` only
- `task:*` matches `task:abc`, `task:xyz`, etc.
- `repo:foo` matches `repo:foo` only

## Wildcard patterns

`capability_audit.py` flags unusual wildcards:

| Pattern | Valid? | Notes |
|---------|--------|-------|
| `global` | ✅ | Standard |
| `task:abc` | ✅ | Exact task |
| `task:*` | ✅ | Wildcard (squad-agent for task queue) |
| `repo:foo` | ✅ | Exact repo |
| `repo:*` | ✅ | Wildcard (cross-repo admin) |
| `task*` (no colon) | ❌ | Flagged — use `task:*` |
| `*` | ❌ | Flagged — too broad |
| `*:*` | ❌ | Flagged — use specific `task:*` or `repo:*` |

If you need a scope like `task*` (no colon), it almost certainly
should be `task:*`. The audit will fail the build and require you
to fix it.

## Constraint field

In addition to `scope`, you can add `constraint` to a capability
entry. Constraints are documentation, not enforced by the runtime —
but `capability_audit.py` warns if sensitive caps lack them.

**Pattern:**
```yaml
- cap: execute-cli-high
  scope: global
  constraint: "no_shell_injection"   # document that this is meant to NOT use shell=True
```

**Sensitive caps that should have constraints:**
- `harness-run` → `constraint: "manifest_required"`
- `execute-cli-high` → `constraint: "no_shell_injection"`
- `modify-infra` → `constraint: "infra_only"` (no random writes)

## Decision tree

```
Want to grant a cap to a role
│
├─ Should the role have it everywhere?
│  └─ YES → scope: global
│
├─ Only in this repo?
│  └─ YES → scope: "repo:NAME"
│
├─ Only for a specific task?
│  └─ YES → scope: "task:ID"
│
└─ For all tasks in the queue?
   └─ YES → scope: "task:*"
```

## Examples from the current matrix

```yaml
infra-agent:
  - { cap: modify-bus,    scope: global }    # bus access everywhere
  - { cap: modify-infra,  scope: global }    # infra anywhere

squad-agent:
  - { cap: modify-tasks,  scope: "task:*" }  # can manage any task

human:
  - { cap: stop-daemon,   scope: global }    # can stop anywhere
```
