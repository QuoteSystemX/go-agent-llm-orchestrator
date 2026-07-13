# Harness Security Review Checklist

Run this before merging any change to `.agent/config/harnesses.yaml`.

## Pre-merge checklist

### 1. Schema validation
- [ ] `bin/harness_run --validate` returns 0 (no errors)
- [ ] `version: "2.0.0"` (not 1.x)
- [ ] `name` is unique, lowercase, no spaces
- [ ] `binary` resolves to an actual file (use `which <binary>` to check)
- [ ] `description` is one line, plain text

### 2. Sandbox enforcement
- [ ] `sandbox.required: true` (mandatory in v2)
- [ ] `sandbox.network` is `"deny"` (or has explicit allowlist)
- [ ] `sandbox.filesystem.write` does NOT include `/`, `~`, or repo root
- [ ] `sandbox.filesystem.read_only` is explicit (not `["/"]`)
- [ ] `sandbox.timeout_s` ≤ 1200 (20 min cap for LLM calls)

### 3. Environment safety
- [ ] `env_passthrough` is MINIMAL (only `PATH`, `HOME`, `USER`, `LANG`, `PWD`)
- [ ] No `LD_*` variables in passthrough
- [ ] No `PYTHONPATH`, `NODE_PATH` (these enable library injection)
- [ ] No `AWS_*` or `*_API_KEY` unless explicitly needed (and that should be rare)

### 4. Args safety
- [ ] `args` are a fixed list, NOT user-controllable
- [ ] No `--config <user_path>` or similar user-controlled flags
- [ ] No `--eval`, `--script`, or code-execution flags
- [ ] Args do not start with `--no-verify`, `--skip-*` (bypasses)

### 5. Capability hygiene
- [ ] `capabilities_required` includes `harness-run`
- [ ] `capabilities_granted` is LEAST PRIVILEGE (don't grant `execute-cli-high` if `execute-cli-low` suffices)
- [ ] `constraint` field present for sensitive caps (`harness-run`, `execute-cli-high`)

### 6. Caller enforcement
- [ ] Tested with `--caller-role session-agent` → must DENY (session-agent has no caps)
- [ ] Tested with `--caller-role human` → must DENY for non-trivial ops
- [ ] Tested with `--caller-role infra-agent` → must ALLOW

### 7. Adversarial scenarios (5 red-team tests)
- [ ] Shell injection in `extra_args` → blocked (`shell=False`)
- [ ] `LD_PRELOAD` injection via env → cleared by sanitizer
- [ ] Filesystem escape via cwd → blocked by chdir
- [ ] Network exfiltration → blocked by `network: deny` (host-level)
- [ ] Privilege escalation via caller_role → blocked by capability check

## Approval matrix

| Change | Required approval |
|--------|-------------------|
| Update existing harness (e.g., bump timeout) | `@harness-runner` + 1 reviewer |
| Add new harness | `@harness-runner` + `@security-auditor` + 1 reviewer |
| Add new capability to operations table | `@permission-guard` + `@security-auditor` |
| Change default `caller_role` policy | `@cto` + ADR |

## Common security pitfalls

1. **`network: allow` without thinking** — Most LLMs need network.
   But: prefer running through a proxy (e.g., LM Studio) with
   `network: restricted` to specific hosts.

2. **`write: ["./"]`** — Allows writing anywhere in the repo. Use
   `["./scratch/"]` instead.

3. **`timeout_s: 0`** — Disables timeout. Always set a value.

4. **Forgetting `capabilities_required: [harness-run]`** — Bypasses the
   capability check entirely.

5. **Args with `$$` or backticks** — Would be expanded in shell. With
   `shell=False` (default), this is safe — but don't use shell!

## Reviewer checklist

When reviewing a PR that touches `harnesses.yaml`:

- [ ] Schema validation passes (`bin/harness_run --validate`)
- [ ] Capability audit passes (`python3 capability_audit.py`)
- [ ] At least 2 reviewers approved (1 must be `@security-auditor`
      for new harnesses)
- [ ] No changes to `sandbox.required: false` (forbidden in v2)
- [ ] No `network: allow` without ADR justification
