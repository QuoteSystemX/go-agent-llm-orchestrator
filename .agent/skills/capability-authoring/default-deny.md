# Default-Deny Principle

The capability matrix is **default-deny**: a role gets NO capabilities
unless explicitly listed. This is a security invariant — every other
property of the matrix is built on this foundation.

## The Invariant

> **`session-agent` capabilities list MUST be empty.**

That is the entire invariant. Everything else follows:

1. If `session-agent` has `[]` (empty list), every `check()` call
   against session-agent returns False.
2. Therefore session-agent cannot do `run_task`, `stop`, `harness_run`,
   or any other privileged op.
3. The daemon's `handle_client` denies such requests with
   `code: CAPABILITY_DENIED`.

## Why this matters

A `session-agent` is the **most common** agent in the kit (49 specialists
run as session-agents). If even one capability is granted, it becomes
a foothold for privilege escalation. For example:

```yaml
session-agent:
  capabilities:
    - { cap: read-tasks, scope: global }  # ⚠️  Looks harmless
```

`read-tasks` alone is fine. But combined with a `squad-agent` that
forwards session-agent output to a privileged action, you have a
side-channel. Default-deny eliminates this attack surface.

## What "default-deny" means in practice

| Scenario | Default-deny behavior |
|----------|-----------------------|
| New operation added to `operations` table | **No role can use it** until you add it to that role's `capabilities` |
| New role added to `roles` | **No capabilities** until you grant them |
| Bug: matrix file missing | `check()` raises exception → fail-closed in `bin/harness_run` and daemon |
| `session-agent` accidentally gets a cap | `capability_audit.py` fails the build |

## What "default-deny" does NOT mean

- It does **not** mean "deny all reads" — `read-*` caps are still granted
  to roles that need them (e.g., `session-agent` is denied even reads
  by default, but `squad-agent` has `read-bus`).
- It does **not** mean "no introspection" — `capability_audit.py` and
  the matrix itself are readable.
- It does **not** mean "no exceptions" — `human` has `stop-daemon` and
  `modify-tasks` because humans are trusted operators. But humans
  still go through the cap check (no implicit admin).

## Common violations to watch for

1. **"Just for testing"** — Someone adds a cap to session-agent in a
   PR. The PR is merged. The cap is forgotten. Now session-agent can
   do that op forever. **Always use a dedicated test role** if you
   need a non-`infra-agent` capability.

2. **"We need it for backward compat"** — Use `human` role instead, or
   create a new role. Never grant session-agent a cap to satisfy
   "backward compat".

3. **"It's read-only, what could go wrong?"** — A `read-*` cap is
   usually fine, but reading the bus gives you access to all
   agent communications. Reading task descriptions gives you the
   code. Information disclosure is a real attack vector.

4. **"The audit script passed locally"** — If you bypass
   `capability_audit.py` (e.g., `--no-verify`), the build still
   succeeds but the invariant is broken. CI runs the audit on every PR.

## How to enforce

1. **Always run** `python3 .agent/scripts/dev/capability_audit.py`
   after editing the matrix. It will fail if `session-agent` is non-empty.
2. **Always require** `@security-auditor` approval for any change to
   the matrix.
3. **Always write an ADR** for adding a new role or new capability
   pattern. ADRs go in `wiki/decisions/`.
4. **Never bypass** the audit. If the audit fails and you think the
   failure is wrong, FIX THE AUDIT, not the matrix.
