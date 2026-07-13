# Harness Examples

Worked examples for common scenarios. Each example shows the diff to
`.agent/config/harnesses.yaml` and the verification steps.

## Example 1: Adding OpenAI Codex (gated behind security review)

Codex is a real LLM CLI but was NOT included in the v2 starter set
because it requires `network: allow`. To enable it:

```yaml
# Add to .agent/config/harnesses.yaml (after the existing claude + free_code entries):

  - name: codex
    binary: codex
    description: "OpenAI Codex CLI (gated: requires security review)"
    capabilities_required:
      - harness-run
    capabilities_granted:
      - execute-cli-high
      - read-bus
      - modify-bus
    sandbox:
      required: true
      network: allow    # ⚠️  Codex needs OpenAI API
      filesystem:
        read_only: ["./", ".agent/"]
        write: ["./scratch/"]
      env_passthrough:
        - PATH
        - HOME
        - USER
        - OPENAI_API_KEY    # ⚠️  Pass the API key
      timeout_s: 600
    model_default: "gpt-5.5"
    args:
      - "--full-auto"
```

**Pre-merge gates:**
- [ ] `@security-auditor` approved the `network: allow` decision
- [ ] `@permission-guard` added `openai-cli` to operations if not present
- [ ] `OPENAI_API_KEY` documented in `.env.example`

**Verify:**
```bash
bin/harness_run --validate
python3 .agent/scripts/dev/capability_audit.py
bin/harness_run --harness codex --prompt-file ./test.md --caller-role infra-agent
```

## Example 2: Adding a custom local model runner

Suppose you have a local tool `my-llm` at `/usr/local/bin/my-llm`:

```yaml
  - name: my-llm
    binary: /usr/local/bin/my-llm
    description: "My local LLM runner (no network)"
    capabilities_required:
      - harness-run
    capabilities_granted:
      - execute-cli-low    # No network → low risk
      - read-bus
    sandbox:
      required: true
      network: deny
      filesystem:
        read_only: ["./"]
        write: ["./scratch/"]
      env_passthrough: [PATH, HOME, USER, LANG]
      timeout_s: 300
    model_default: "my-model-7b"
    args:
      - "--quiet"
      - "--no-color"
```

**Verify the binary exists:**
```bash
ls -l /usr/local/bin/my-llm
which my-llm  # alternative check
```

## Example 3: Updating an existing harness (e.g., bumping timeout)

If claude is timing out on long tasks, change the timeout:

```yaml
# Before:
    timeout_s: 600

# After:
    timeout_s: 1200
```

**Verify:**
```bash
bin/harness_run --manifest claude  # show the new value
bin/harness_run --validate         # ensure schema still valid
```

## Example 4: Debugging CAPABILITY_DENIED

**Error:**
```json
{
  "code": "CAPABILITY_DENIED",
  "caller_role": "session-agent",
  "required_capability": "harness-run"
}
```

**Diagnosis:**
- `session-agent` is **default-deny** (intentional)
- `session-agent` capabilities list is `[]` in `capabilities.yaml`
- So `session-agent` cannot invoke any harness — by design

**Fix (if legitimate):** The caller should not be `session-agent`.
Use `--caller-role infra-agent` or `--caller-role squad-agent`.

**Fix (if matrix wrong):** Add the cap to the appropriate role, e.g.,
```yaml
roles:
  squad-agent:
    capabilities:
      - { cap: harness-run, scope: global }  # ADD
```

Then `bin/harness_run --harness my-tool --caller-role squad-agent` will work.

## Example 5: OTel span inspection

When `bin/harness_run` executes, it emits a JSON span to stderr:

```json
[OTEL-SPAN] {"name": "harness.invoke", "ts": 1783777748.88, "attributes": {
  "harness.name": "claude",
  "harness.binary": "claude",
  "prompt.size_bytes": 4787,
  "prompt.sha256": "a39ac71f30738d69",
  "caller.role": "infra-agent",
  "scope": "global",
  "exit.code": 0,
  "duration.ms": 5432,
  "stdout.size": 12345,
  "stderr.size": 0,
  "sandbox.violations": 0
}}
```

To collect these, redirect stderr to a file:
```bash
bin/harness_run --harness claude --prompt-file ./task.md \
    --caller-role infra-agent 2>>.agent/bus/otel_spans.jsonl
```

The `[OTEL-SPAN]` line is grep-able for log aggregation.
