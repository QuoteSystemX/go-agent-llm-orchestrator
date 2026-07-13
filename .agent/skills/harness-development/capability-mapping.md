# Capability Mapping for Harnesses

Every harness entry in `harnesses.yaml` declares two sets of capabilities:

- `capabilities_required` — caps the **CALLER** must have
- `capabilities_granted` — caps the **HARNESS** has within its sandbox

These are different from the role capabilities in
`capabilities.yaml` (which is the matrix for agents). Together they
form a layered security model.

## How the chain works

```
Caller (e.g., @harness-runner, role=infra-agent)
   │
   │ 1. bin/harness_run checks: does role have "harness-run"?
   │    If NO → return CAPABILITY_DENIED
   │
   │ 2. Manifest loaded. Harness entry has:
   │    capabilities_required: [harness-run]
   │    capabilities_granted: [execute-cli-low, read-bus]
   │
   │ 3. Sandbox spawned with granted capabilities.
   │    The harness can now do execute-cli-low and read-bus.
   │
   ↓
Subprocess runs with restricted environment
```

## `capabilities_required` — what to put

At minimum, include `harness-run`. The harness-runner (caller) will
have this in its role capabilities.

```yaml
capabilities_required:
  - harness-run
```

## `capabilities_granted` — what to put

Think about what the binary needs to do **within its sandbox**:

| Harness behavior | Grant this cap |
|------------------|----------------|
| Reads files only | `read-infra`, `read-bus` |
| Writes files (e.g., saves a draft) | `modify-bus` |
| Runs shell commands | `execute-cli-low` or `execute-cli-high` |
| Makes HTTP calls to LLM API | `execute-cli-high` (with `network: allow`) |
| Spawns subagents | `harness-run` (nested) |

For claude (autonomous agent), grant:
```yaml
capabilities_granted:
  - execute-cli-high
  - read-bus
  - modify-bus
```

For free_code (simpler, no network), grant:
```yaml
capabilities_granted:
  - execute-cli-low
  - read-bus
```

## The constraint field

For sensitive caps (`harness-run`, `execute-cli-high`), add a
`constraint` field documenting the safety check:

```yaml
capabilities_granted:
  - execute-cli-high
    constraint: "no_shell_injection"
  - harness-run
    constraint: "manifest_required"
```

The `capability_audit.py` script will warn if these are missing.

## Pre-deploy verification

After editing capabilities_required/granted:

```bash
# 1. Validate manifest schema
bin/harness_run --validate

# 2. Run pre-deploy audit (checks matrix consistency)
python3 .agent/scripts/dev/capability_audit.py

# 3. Test with a real call (use infra-agent role)
bin/harness_run --harness my-tool --prompt-file ./test.md --caller-role infra-agent
```

If the call returns `code: CAPABILITY_DENIED`, your caller role
doesn't have the required cap, or the matrix is missing it.
