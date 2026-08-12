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
   ├─→ spawn binary via subprocess.run (shell=False), enforced:
   │      ├─ rlimits: memory/CPU/file-size via preexec_fn (real)
   │      ├─ env sanitization: minimal PATH, no LD_PRELOAD (real)
   │      ├─ network policy: declared in manifest, NOT enforced here
   │      └─ fs policy: declared in manifest, NOT enforced here
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
    timeout_s=None,                         # optional; can only shrink the manifest's timeout_s, never extend it
)
# No extra_args — removed 2026-08-12 (flag injection into the harness's own
# CLI; contradicted the "no per-call args" line under Out of Scope below).
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

`--caller-role` has no default — omitting it on an actual run (not `--list`/`--manifest`/`--validate`) is a hard CLI error, not a silent grant.

### Required Environment

- `HARNESS_MANIFEST` (default: `.agent/config/harnesses.yaml`)
- `HARNESS_CWD` (default: `REPO_ROOT`) — where the binary runs
- `HARNESS_SCRATCH` (default: `./scratch`) — writable directory

### Sandbox Integration

**Correction (2026-08-12)**: earlier revisions of this doc claimed v2 reused
`sandbox_runner._apply_limits()` (from `.agent/scripts/chaos/sandbox_runner.py`).
It never did — that function mutates the rlimits of whatever process *imports*
it (designed for in-process fuzz-test rlimiting), not a spawned subprocess;
`harness_run.py` never imported or called it. What's actually implemented,
directly in `harness_run.py` (`_prepare_env_and_timeout`, `_build_rlimit_enforcement`,
`_make_rlimit_preexec`, `_check_rlimit_feasibility`):

1. **Real, enforced**: `resource.setrlimit` for `RLIMIT_AS` (memory),
   `RLIMIT_CPU`, `RLIMIT_FSIZE` — applied to the spawned subprocess via
   `preexec_fn`, best-effort (a limit the host already caps tighter than our
   request doesn't abort the run — it's already *more* restricted, which is
   safe). Defaults: 4096 MB address space, 1024 MB max file size, CPU seconds
   = actual (already-clamped) wall-clock timeout + 30s buffer; overridable
   per-harness via an optional `sandbox.rlimits: {as_mb, fsize_mb}` manifest
   block. A pre-flight check (`_check_rlimit_feasibility`) reads the current
   process's hard ceilings *before* spawning and reports any requested limit
   that can't actually be achieved into `HarnessResult.sandbox_violations` —
   this is the only point where feasibility can be verified without extra
   IPC to the forked child; a `setrlimit` that fails inside the child for a
   *different* reason (e.g. a seccomp filter denying the syscall outright)
   is swallowed silently by design (see Threat Model note below) and won't
   show up here.
2. **Real, enforced**: a caller-supplied `timeout_s` can only *shrink* the
   manifest's declared `sandbox.timeout_s`, never extend it (`run()` clamps
   via `min()`) — otherwise a caller could pass an unbounded value and
   defeat the manifest's declared "hard cap". Descendant processes are
   bounded too: the subprocess is spawned in its own session
   (`start_new_session=True`); on timeout the whole process group is
   `SIGKILL`ed via `os.killpg`, not just the direct child — `subprocess.run`'s
   built-in timeout handling only kills the immediate child, leaving any
   grandchild the harness binary forks to outlive the cap.
3. **Real, enforced**: `os.environ` sanitization — sanitized env is built from
   an explicit `env_passthrough` allowlist plus `PATH`; known-dangerous vars
   (`LD_PRELOAD`, `LD_LIBRARY_PATH`, `PYTHONPATH`, etc.) are explicitly
   cleared regardless (`_build_sanitized_env`). The manifest binary name is
   also resolved (`shutil.which`) against this *sanitized* PATH, not the
   invoking process's live PATH — resolving against the parent's PATH would
   let anything writable earlier in it shadow the real binary.
4. **Real, enforced**: `--caller-role` has no default at the CLI layer — a
   missing flag is a hard error, not a silent grant. It previously defaulted
   to `infra-agent` (the highest-trust role), so any invocation that omitted
   the flag ran with full access instead of being denied.
5. **Removed rather than fixed**: the `extra_args` parameter/`--extra-args`
   flag, which let any capability-checked caller append arbitrary argv
   tokens to the harness binary's own CLI (flag injection — distinct from,
   and not mitigated by, the `shell=False` defense against shell injection).
   This directly contradicted the "no per-call args other than what's
   declared" line under Out of Scope below; the code just hadn't matched it.
   Nothing in this repo called it, so it was deleted rather than sanitized.
6. **NOT enforced at the Python layer — host-level only, if at all**:
   filesystem read-only/write policy (only `cwd` is set to scratch-or-repo-
   root; no chroot/namespace/permission restriction) and network `deny`
   policy (a manifest field that's read back and logged in the OTel span,
   nothing actually blocks an outbound connection). These are **not**
   guaranteed by anything in this repo — see "Out of Scope" below, and don't
   treat the manifest's `filesystem`/`network` fields as active controls.

**Known caveats (not fixed, tracked for follow-up):**
- `preexec_fn` is [documented by CPython as unsafe under threads](https://docs.python.org/3/library/subprocess.html#subprocess.Popen) (fork-time deadlock risk). If a future caller invokes `run()` concurrently from multiple threads in the same process, this becomes a real self-DoS surface. Current callers are single-threaded CLI/daemon-loop invocations; multithreaded callers should use process-level or `asyncio`-based concurrency instead, not threads calling `run()` directly.
- `capture_output`-equivalent output capture (`stdout=PIPE, stderr=PIPE` + `communicate()`) buffers the full stdout/stderr of the child in the *unsandboxed* `harness_run.py` process itself. `RLIMIT_AS` bounds the child's own memory, not what the parent buffers while reading the pipe — a compliant, rlimit-abiding child can still stream several GB before the digest is computed. Not fixed in this pass; would need incremental/size-capped reading instead of `communicate()`.

### OTel Spans

Every `run()` emits one span: `harness.invoke` with attributes:

- `harness.name`: from manifest
- `harness.binary`: absolute path
- `prompt.size_bytes`: int
- `prompt.sha256`: 16 hex chars
- `caller.role`: from caller
- `exit.code`: from process
- `duration.ms`: int
- `sandbox.violations`: int — count of rlimits the pre-flight feasibility check found unachievable given the current process's hard ceilings (see Sandbox Integration above). NOT a measure of filesystem/network policy violations — those aren't enforced, so there's nothing to detect a violation of.

Spans go to stderr (default) or OTLP endpoint (if `OTEL_EXPORTER_OTLP_ENDPOINT` set). The OTel SDK is NOT a hard dependency — v2 uses a minimal stdout-based tracer to avoid the 200MB+ SDK install.

### Capabilities

- **Caller must have `harness-run` capability** for the requested scope (default-deny via STORY-4)
- The matrix lives in `.agent/config/capabilities.yaml` (existing)
- Roles: `infra-agent` (full), `squad-agent` (constrained), `session-agent` (deny), `human` (deny by default)

### Threat Model

| Threat | Mitigation |
|---|---|
| RCE via shell injection in `cmd` | Manifest is YAML, NOT a string. `cmd` is a list. `subprocess.run([...])` with list args. **No shell.** |
| Resource exhaustion (memory/CPU/disk) | `_make_rlimit_preexec` sets `RLIMIT_AS`/`RLIMIT_CPU`/`RLIMIT_FSIZE` on the child via `preexec_fn`. `_check_rlimit_feasibility` verifies achievability against the current process's hard ceilings *before* spawning and reports gaps in `sandbox_violations`. |
| Network exfiltration | ⚠️ **NOT enforced.** Manifest declares `network: deny`; that's a logged, unenforced field. No netns/seccomp/iptables rule exists in this codebase. Host-level enforcement, if any, is outside this repo's scope. |
| Filesystem escape | ⚠️ **NOT enforced.** `cwd` is set to scratch-or-repo-root, but nothing stops a subprocess from reading/writing an absolute path outside the declared `read_only`/`write` lists — no chroot/namespace/permission restriction exists. |
| Env injection (LD_PRELOAD) | Manifest declares `env_passthrough` whitelist. `os.environ` filtered. **No passthrough = minimal env.** |
| Prompt injection via prompt file | File is read and passed via `--prompt-file` (or stdin). **The harness binary is responsible for its own prompt sanitization.** This contract does NOT sanitize the prompt content — that's the harness's job. |
| TOCTOU on prompt file | File is read once into a string and passed as a file path. Caller is responsible for the file's integrity. |
| Privilege escalation via caller_role | Capability check is mandatory; missing role = denied. `--caller-role` has no CLI default (was `infra-agent` — highest trust — until 2026-08-12; a missing flag is now a hard error, not a silent full-access grant). |
| Flag injection into the harness's own CLI | `extra_args` (a caller-controlled param that appended arbitrary argv tokens, e.g. a permissions-bypass flag) was removed 2026-08-12 — the manifest's declared `args` is the only argv besides `--model`/prompt path. |
| Unbounded wall-clock via caller-supplied timeout | `timeout_s` passed to `run()`/`--timeout-s` can only shrink the manifest's declared ceiling (`min()`), never extend it. |
| Resource exhaustion via forked grandchildren | Subprocess spawned in its own session (`start_new_session=True`); on timeout the whole process group is killed (`os.killpg`), not just the direct child. |
| PATH hijack of a bare manifest binary name | Binary resolution (`shutil.which`) uses the sanitized env's PATH, not the invoking process's live PATH. |
| Backward compat with `ANIMA_HARNESS_CMD` | **NOT supported in v2.** Use `harnesses.yaml`. A one-time deprecation warning is logged if `ANIMA_HARNESS_CMD` is set. |

### Rollback Plan

If v2 proves problematic:

1. Revert `bin/harness_run`, `harnesses.yaml`, `HARNESS_CONTRACT.md`
2. Keep ADR-008 as historical record
3. Existing CLI tools (`claude`, `codex`, `free-code`) continue to work via direct invocation — no contract change for them

### Out of Scope (deferred)

- ⚠️ **Network enforcement** — `network: deny` in the manifest is declared-intent/audit metadata only. Nothing in this repo blocks an outbound connection; a real control (iptables, K8s NetworkPolicy, netns) would have to live at the host/infra level, outside this codebase, and isn't currently wired up anywhere known.
- ⚠️ **Filesystem enforcement** — `filesystem.read_only`/`write` in the manifest are declared-intent/audit metadata only. Nothing stops a subprocess from reading or writing any absolute path it has OS-level permission to touch; a real control would need chroot/namespaces/seccomp, none of which exist here.
- Auto-discovery of new harnesses (manifest is static)
- MCP tool wrapper (would require Go broker fix; separate epic)
- Rate limiting / quota per harness (deferred to future epic)

Per-prompt argument injection is **not** deferred — it's enforced: the manifest is fixed per harness, no per-call args other than `--model`/prompt path (see `extra_args` removal above; this used to say "out of scope" while the code allowed exactly that).

## Compliance with Council of Sages Verdicts

| Sage | Concern | Addressed by |
|---|---|---|
| red-team | RCE via shell injection | Manifest is YAML, `subprocess.run(list)` — no shell |
| red-team | Env injection | Manifest env_passthrough whitelist, filter dangerous vars |
| risk-manager | Catastrophic blast | Capability check (default-deny) + rlimits (memory/CPU/fsize, real). FS/network policy are declared-intent only, **not enforced** — see Sandbox Integration and Out of Scope. |
| meta-architect | Pure function boundary | Manifest-driven; CLI in, structured trace out, env sandboxed |
| meta-architect | OTel spans for distillation | `harness.invoke` span on every run |
| reviewer | Backward compat | `ANIMA_HARNESS_CMD` is **NOT** supported in v2 (clean break) |
| CTO | GO-WITH-CHANGES, effort +1.5d | 2.5d is within budget |
| security-auditor | Re-run 2026-08-12 against the corrected code/docs. Findings: fail-open `--caller-role` default (High, fixed), descendant processes outliving timeout (High, fixed), silent child-side rlimit failure with no signal (Medium, documented as a known caveat), PATH-hijack via bare binary names (Medium, fixed), unbounded parent-side output buffering (Medium, deferred — needs incremental/capped reads instead of `communicate()`). | Addressed inline above; see git history for the full report. |
| red-team | Re-run 2026-08-12. Findings: `--caller-role` CLI default was Critical (self-asserted highest-trust role, untested), `extra_args` flag injection (High, removed), caller-controlled `timeout_s` decoupled RLIMIT_CPU from the wall-clock cap it was supposed to back (High, fixed — cpu derived from the clamped actual timeout), `preexec_fn` thread-unsafety under a hypothetical multithreaded caller (Medium, documented as a known caveat). No new bypass found for capability default-deny, env sanitization, or shell-injection defenses — those hold as designed. | Addressed inline above; see git history for the full report. |
