# Audit Checklist (Pre-merge Gate)

Run this checklist before committing any change to
`.agent/config/capabilities.yaml`. The CI step
`python3 .agent/scripts/dev/capability_audit.py` enforces most of this
automatically, but the manual review is still required.

## Pre-commit checklist

### 1. Schema validation
- [ ] `version: "1.0.0"` (only supported version)
- [ ] `roles:` is a YAML mapping (not list)
- [ ] `operations:` is a YAML mapping
- [ ] All roles have a `capabilities:` key (can be empty list)

### 2. Default-deny invariant (CRITICAL)
- [ ] `session-agent` capabilities is `[]` or has no real entries
- [ ] No new role has been added with broad caps without an ADR
- [ ] `human` is NOT used to bypass caps for `session-agent`

### 3. Required operations
- [ ] All required operations are present in `operations:` table
- [ ] Each operation's cap name is also declared in at least one role
- [ ] No "orphan" operations (declared but no role has the cap)

### 4. Cap hygiene
- [ ] All `capabilities_required` in harnesses.yaml match a cap in
      this matrix
- [ ] No dead caps (in role capabilities but not in operations)
- [ ] No cap name typos (e.g., `modfiy-tasks` vs `modify-tasks`)

### 5. Scope patterns
- [ ] No `*` or `*:*` (too broad)
- [ ] No `task*` without colon (use `task:*`)
- [ ] Only `global`, `repo:NAME`, `task:ID`, `task:*` patterns used
- [ ] Wildcards (`task:*`, `repo:*`) only when intentional

### 6. Constraints
- [ ] `harness-run` entries have `constraint: "manifest_required"`
- [ ] `execute-cli-high` entries have `constraint: "no_shell_injection"`
- [ ] `modify-infra` entries have `constraint` documented

### 7. Documentation
- [ ] If you added a new role, write an ADR in `wiki/decisions/`
- [ ] If you added a new capability, document it in this skill
- [ ] If you changed a `constraint`, update `.agent/HARNESS_CONTRACT.md`

## How to run the audit

```bash
# 1. Run the audit (must pass)
python3 .agent/scripts/dev/capability_audit.py
# Expected output:
#   🔍 Capability audit: capabilities.yaml (v1.0.0)
#      Status: ✅ PASS
#      Issues: 0  Warnings: 0

# 2. Run as JSON (for CI)
python3 .agent/scripts/dev/capability_audit.py --json | jq '.passed'
# Expected: true

# 3. Run with strict (warnings become errors)
python3 .agent/scripts/dev/capability_audit.py --strict
# Expected: exit 0 if no warnings, 1 if any
```

## What to do if audit fails

1. **Read the error message** — it tells you which check failed
2. **Look at the offending section** of `capabilities.yaml`
3. **Fix the issue**:
   - `session-agent` has caps → set to `[]`
   - Missing operation → add to `operations:` table
   - Cap drift → align role caps with operations
   - Wildcard issue → fix the pattern
4. **Re-run the audit** until it passes
5. **Commit the fix** with a clear message

## Common audit failures

| Error | Fix |
|-------|-----|
| `session-agent has 1 capability(ies) — should be empty` | Remove the cap, use a different role |
| `required operation missing: 'task_write'` | Add `task_write: modify-tasks` to operations |
| `dead capabilities (declared in roles but not in operations)` | Either add to operations or remove from role |
| `unusual wildcard pattern` | Change `task*` to `task:*` |
| `sensitive cap 'harness-run' missing 'constraint' field` | Add `constraint: "manifest_required"` |
| `unsupported version '0.9.0'` | Update to `"1.0.0"` |

## Pre-merge approvals

| Change type | Required approvals |
|-------------|---------------------|
| Add cap to existing role | 1 reviewer |
| Add new role | `@security-auditor` + ADR + 1 reviewer |
| Add new operation | `@permission-guard` + 1 reviewer |
| Change `session-agent` capabilities (even to add) | `@security-auditor` + ADR + `@cto` |
| Change `human` capabilities | `@cto` |
| Change constraints (without changing caps) | 1 reviewer |
