# HARNESS_CONTRACT.md v2 — STORY-5 (REWORK of VETO 3.5)

**Status**: Accepted
**Date**: 2026-07-11
**Deciders**: @orchestrator, @meta-architect, @risk-manager, @red-team, @security-auditor
**Supersedes**: v1 from plan, VETOED by red-team + risk-manager
**Related**:
- [STORY-5 in epic card](../../tasks/2026-07-11-epic-integration-anima-sdk-v2-a27f5a.md)
- [ADR-008](ADR-008-harness-run-v2-capability.md)
- [capabilities.yaml](../config/capabilities.yaml) (STORY-4)

## Background

v1 of `harness_run` was a "drop in any CLI" design with no safety constraints. Council of Sages unanimously rejected it:

- **red-team (CRITICAL)**: Arbitrary Command Execution via shell-injection in `cmd` parameter
- **risk-manager (VETO)**: Catastrophic blast radius + impossible rollback
- **meta-architect**: Required "pure function boundary" with capability manifest
- **reviewer**: Backward compat issues

v2 adopts **defense-in-depth**: declarative capability manifest, mandatory capability check, sandbox, network/FS/env policy, OTel spans.

## v2 Design

### Architecture

```
human/cli
   │
   ↓ bin/harness_run --harness claude --prompt-file ./task.md
   │
harness_run.py (Python)
   │
   ├─→ load manifest from harnesses.yaml
   ├─→ check(matrix, caller_role, "harness_run", scope)   ← STORY-4 default-deny
   ├─→ validate manifest schema
   ├─→ spawn binary in sandbox_runner
   │      ├─ network policy: default-deny
   │      ├─ fs policy: read-only outside scratch
   │      └─ env sanitization: minimal PATH, no LD_PRELOAD
   ├─→ OTel span: harness.invoke { name, prompt_size, exit_code, duration_ms }
   ├─→ capture result.json: { exit_code, stdout_digest, stderr_digest, duration_ms, sandbox_violations[] }
   └─→ return result to caller
```

### Capability Manifest Schema (in `harnesses.yaml`)

```yaml
- name: <unique-harness-name>             # e.g., "claude", "free_code"
  binary: <path-to-executable>             # absolute or PATH-relative
  description: <one-line>
  capabilities_required:                   # what the harness needs to be invoked
    - modify-bus                            # at least one of these must be in the caller's role
  capabilities_granted:                    # what the harness can do within its sandbox
    - execute-cli-low
  sandbox:
    required: true                         # always true in v2 (v1's `sandbox: required: false` is removed)
    network: deny                          # default deny
    filesystem:
      read_only:                           # paths read-only (default: deny write outside scratch)
        - "./"
        - ".agent/"
      write:                               # paths writable (default: deny)
        - "./scratch/"
    env_passthrough: []                    # explicitly list; empty = minimal PATH only
    timeout_s: 600                          # hard cap
  model_default: <string>                  # optional: pre-fill ANIMA_MODEL
  args: []                                 # extra args to pass
```

### Caller API

```python
from harness_run import run, HarnessResult

result = run(
    name="claude",                          # required
    prompt_file="./task.md",                # required, must exist, size-limited
    caller_role="infra-agent",              # required, checked against capabilities.yaml
    scope="global",                         # default: global
    model=None,                             # optional, overrides manifest default
    timeout_s=None,                         # optional, overrides manifest default
    extra_args=[],                          # optional, appended to manifest args
)
# result: HarnessResult
assert result.exit_code == 0
assert result.stdout_digest  # sha256 of stdout (truncated to 64 chars)
```

### CLI

```bash
bin/harness_run --harness claude --prompt-file ./task.md --caller-role infra-agent
bin/harness_run --list                     # show all manifests
bin/harness_run --manifest claude          # show one manifest
bin/harness_run --validate                 # validate all manifests
```

### Required Environment

- `HARNESS_MANIFEST` (default: `.agent/config/harnesses.yaml`)
- `HARNESS_CWD` (default: `REPO_ROOT`) — where the binary runs
- `HARNESS_SCRATCH` (default: `./scratch`) — writable directory

### Sandbox Integration

v2 reuses the existing `sandbox_runner._apply_limits()` from prior security work. The runner adds:

1. `resource.setrlimit` for CPU time, memory, file size
2. `os.environ` whitelist (only `PATH`, `HOME`, `USER`, `LANG`, `PWD`, `HARNESS_*`)
3. Drop dangerous env vars: `LD_PRELOAD`, `LD_LIBRARY_PATH`, `PYTHONPATH` (set to `''`)
4. Chdir to sandbox dir before exec
5. Network policy: documented in manifest; **enforcement is host-level** (e.g., iptables on Linux, NetworkPolicy in K8s). The Python layer logs the policy but cannot guarantee it.

### OTel Spans

Every `run()` emits one span: `harness.invoke` with attributes:

- `harness.name`: from manifest
- `harness.binary`: absolute path
- `prompt.size_bytes`: int
- `prompt.sha256`: 16 hex chars
- `caller.role`: from caller
- `exit.code`: from process
- `duration.ms`: int
- `sandbox.violations`: int (from sandbox_runner)

Spans go to stderr (default) or OTLP endpoint (if `OTEL_EXPORTER_OTLP_ENDPOINT` set). The OTel SDK is NOT a hard dependency — v2 uses a minimal stdout-based tracer to avoid the 200MB+ SDK install.

### Capabilities

- **Caller must have `harness-run` capability** for the requested scope (default-deny via STORY-4)
- The matrix lives in `.agent/config/capabilities.yaml` (existing)
- Roles: `infra-agent` (full), `squad-agent` (constrained), `session-agent` (deny), `human` (deny by default)

### Threat Model

| Threat | Mitigation |
|---|---|
| RCE via shell injection in `cmd` | Manifest is YAML, NOT a string. `cmd` is a list. `subprocess.run([...])` with list args. **No shell.** |
| Sandbox bypass | `sandbox_runner._apply_limits()` with hybrid fail-fast + best-effort. `getrlimit` verification + warnings in result. |
| Network exfiltration | Manifest declares `network: deny`. Enforcement is host-level (iptables/K8s). Python layer logs and reports. |
| Filesystem escape | `os.chdir(sandbox)` before exec. Writable paths declared in manifest. `subprocess.run` inherits cwd. |
| Env injection (LD_PRELOAD) | Manifest declares `env_passthrough` whitelist. `os.environ` filtered. **No passthrough = minimal env.** |
| Prompt injection via prompt file | File is read and passed via `--prompt-file` (or stdin). **The harness binary is responsible for its own prompt sanitization.** This contract does NOT sanitize the prompt content — that's the harness's job. |
| TOCTOU on prompt file | File is read once into a string and passed as a file path. Caller is responsible for the file's integrity. |
| Privilege escalation via caller_role | Capability check is mandatory; missing role = denied. |
| Backward compat with `ANIMA_HARNESS_CMD` | **NOT supported in v2.** Use `harnesses.yaml`. A one-time deprecation warning is logged if `ANIMA_HARNESS_CMD` is set. |

### Rollback Plan

If v2 proves problematic:

1. Revert `bin/harness_run`, `harnesses.yaml`, `HARNESS_CONTRACT.md`
2. Keep ADR-008 as historical record
3. Existing CLI tools (`claude`, `codex`, `free-code`) continue to work via direct invocation — no contract change for them

### Out of Scope (deferred)

- Host-level network enforcement (iptables/K8s NetworkPolicy) — Python layer only logs
- Auto-discovery of new harnesses (manifest is static)
- MCP tool wrapper (would require Go broker fix; separate epic)
- Per-prompt argument injection (the manifest is fixed per harness; no per-call args other than what's declared)
- Rate limiting / quota per harness (deferred to future epic)

## Compliance with Council of Sages Verdicts

| Sage | Concern | Addressed by |
|---|---|---|
| red-team | RCE via shell injection | Manifest is YAML, `subprocess.run(list)` — no shell |
| red-team | Env injection | Manifest env_passthrough whitelist, filter dangerous vars |
| risk-manager | Catastrophic blast | Sandbox + FS policy + network policy + capability check |
| meta-architect | Pure function boundary | Manifest-driven; CLI in, structured trace out, env sandboxed |
| meta-architect | OTel spans for distillation | `harness.invoke` span on every run |
| reviewer | Backward compat | `ANIMA_HARNESS_CMD` is **NOT** supported in v2 (clean break) |
| CTO | GO-WITH-CHANGES, effort +1.5d | 2.5d is within budget |
| security-auditor (deferred) | TBD | Will be reviewed in production rollout |
