---
name: capability-authoring
description: How to edit the capability matrix at .agent/config/capabilities.yaml. Covers default-deny principles, role definition, scope patterns, capability_audit gates, and ADR workflow. Use when adding a new role, new operation, new capability, or when investigating CAPABILITY_DENIED errors.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
version: 1.0.0
files: audit-checklist.md, default-deny.md, role-patterns.md, scope-patterns.md, scripts/capability_validate.py
---

# Capability Authoring

> How to author the capability matrix that governs every privileged
> action in the kit. The matrix enforces **default-deny**: a role
> without explicit caps cannot do privileged ops.
> **Read this BEFORE editing `.agent/config/capabilities.yaml`.**

## 🎯 When to Use This Skill

- Adding a new role (e.g., `monitor-agent`)
- Adding a new operation key (e.g., `bus_publish`)
- Granting a capability to an existing role
- Investigating `CAPABILITY_DENIED` errors
- Pre-deploy audit: `python3 .agent/scripts/dev/capability_audit.py`
- Deciding between granting a cap vs. adding a constraint

## 📑 Content Map

| File | Description | When to Read |
|------|-------------|--------------|
| `default-deny.md` | The core principle: why session-agent is empty | First-time matrix editor |
| `role-patterns.md` | Reusable role patterns: infra-agent, squad-agent, session-agent, human | Adding/modifying a role |
| `scope-patterns.md` | `global`, `repo:NAME`, `task:ID`, `task:*` | Granting a scoped capability |
| `audit-checklist.md` | Pre-merge gate | Before committing matrix change |

---

## 🚨 RED FLAGS (Stop and Ask)

STOP if you are about to:
- Add ANY capability to `session-agent` (violates default-deny invariant)
- Grant a cap with scope `*` or `*:*` (too broad)
- Grant `execute-cli-high` without `constraint: no_shell_injection`
- Bypass `capability_audit.py` failures "to ship faster"

If you must violate one of these, write an ADR first.

## 🚫 ANTI-PATTERNS (Common Mistakes)

### 1. "Just for testing" → cap leaks into production
A developer adds a cap to `session-agent` "just to make the test pass", merges the PR, and the cap stays. Now session-agent can do that op forever. **Always use a dedicated test role** (e.g., `test-runner-agent`) if you need a non-`infra-agent` capability.

### 2. "Backward compat" → wrong role
A consumer expects `session-agent` to be able to do something. Instead of granting that role the cap, **change the caller to use a more privileged role** (e.g., `squad-agent`) or create a new role.

### 3. Read-only is fine
A read-* cap is usually fine — but reading the bus exposes agent communications, and reading task descriptions exposes code. Information disclosure is a real attack vector. **Treat read-* as privilege, not as free.**

### 4. Audit is optional
`capability_audit.py` failures block the PR. **Never use `--no-verify`** to bypass it. If the audit is wrong, **fix the audit** (e.g., add a new required operation to the list).

### 5. Wildcard scope "to save typing"
`scope: "*"` looks like "anywhere" but the audit will flag it. Use:
- `scope: global` (no restriction)
- `scope: "task:*"` (any task)
- `scope: "repo:NAME"` (specific repo)
- `scope: "task:ID"` (specific task)

### 6. "Fail-open" in production
The daemon's `_check_capability` fails open if the matrix is missing. This is a temporary safety net for unset environments, NOT a production feature. **Always commit the matrix.**

### 7. Modifying harness_run instead of the matrix
If a harness's required cap is denied, the bug is in the matrix (missing op or missing role cap), NOT in `harness_run.py`. Modify the matrix. The runner's cap check is the last line of defense.

### 8. Adding `constraint` to bypass audit
The `constraint` field is documentation, not enforced. Don't add a meaningless constraint just to make `capability_audit.py` happy. **Write the real constraint** ("manifest_required", "no_shell_injection", "infra_only", etc.).

## 🛠️ TOOLS

This skill includes a `scripts/` directory with helper tools:

- `scripts/capability_validate.py` — standalone validator (no audit module import)
  Run before committing matrix changes. Usage:
  ```
  python3 scripts/capability_validate.py [--strict] [--json] [path/to/matrix.yaml]
  ```
  Exit code 0 = valid, 1 = has issues, 2 = config error.

The validator wraps `capability_audit.py` and adds JSON output + strict mode.

## 📋 Quick Reference

```bash
# Validate the matrix
python3 .agent/scripts/dev/capability_audit.py

# Run as a specific role (from Python)
python3 -c "
from .agent.scripts.permissions.capability_check import load_matrix, check
m = load_matrix()
print('infra-agent can harness_run:', check(m, 'infra-agent', 'harness_run'))
print('session-agent can harness_run:', check(m, 'session-agent', 'harness_run'))
"

# Find a CAPABILITY_DENIED source
grep -r "CAPABILITY_DENIED" .agent/bus/  # look for denial events
```

## 📚 Key References

- `.agent/config/capabilities.yaml` — the matrix
- `.agent/scripts/permissions/capability_check.py` — runtime check
- `.agent/scripts/dev/capability_audit.py` — pre-deploy audit
- `wiki/decisions/` — ADRs about prior cap decisions
- `.agent/HARNESS_CONTRACT.md` — harness-side cap requirements
- `.agent/skills/harness-development/` — sister skill
