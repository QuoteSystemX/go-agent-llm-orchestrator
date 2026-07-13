# Harness Manifest Schema

The manifest at `.agent/config/harnesses.yaml` is a YAML list. Each
entry declares a single executable that can be invoked through
`bin/harness_run` (STORY-5).

## Top-level structure

```yaml
version: "2.0.0"           # Required. Must be in SUPPORTED_VERSIONS.
harnesses:                # Required. List of entries (see below).
  - name: <str>            # Unique within file. Lowercase, no spaces.
    ...
  - name: <str>
    ...
```

## Per-entry schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | YES | Unique identifier. Used as `--harness <name>` in CLI. |
| `binary` | string | YES | Absolute path OR PATH-relative executable name. |
| `description` | string | YES | One-line purpose. Shown in `bin/harness_run --list`. |
| `capabilities_required` | list[string] | YES | Caps the CALLER must have. Non-empty. |
| `capabilities_granted` | list[string] | YES | Caps the harness has within its sandbox. |
| `sandbox` | object | YES | Sandbox policy (see below). |
| `model_default` | string | no | Default model to pass via `--model`. |
| `args` | list[string] | YES | Default args appended before prompt file. |

### `sandbox` sub-object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `required` | bool | YES | Must be `true` in v2. No opt-out. |
| `network` | string | YES | `"deny"` (default), `"allow"`, or `"restricted"`. |
| `filesystem` | object | YES | FS policy (see below). |
| `env_passthrough` | list[string] | YES | Whitelist of env vars to pass through. |
| `timeout_s` | int | YES | Hard cap. Recommended: 60-1200. |

### `filesystem` sub-object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `read_only` | list[string] | YES | Paths readable. Default: `["./"]`. |
| `write` | list[string] | YES | Paths writable. Default: `["./scratch/"]`. |

## Minimal example

```yaml
- name: my-tool
  binary: my-tool
  description: "My custom LLM tool"
  capabilities_required:
    - harness-run
  capabilities_granted:
    - execute-cli-low
  sandbox:
    required: true
    network: deny
    filesystem:
      read_only: ["./"]
      write: ["./scratch/"]
    env_passthrough: [PATH, HOME, USER]
    timeout_s: 300
  args: []
```

## Full example (claude)

```yaml
- name: claude
  binary: claude
  description: "Anthropic Claude Code CLI (autonomous agent)"
  capabilities_required:
    - harness-run
  capabilities_granted:
    - execute-cli-high
    - read-bus
    - modify-bus
  sandbox:
    required: true
    network: deny
    filesystem:
      read_only:
        - "./"
        - ".agent/"
      write:
        - "./scratch/"
    env_passthrough:
      - PATH
      - HOME
      - USER
      - LANG
      - PWD
    timeout_s: 600
  model_default: ""
  args:
    - "--print"
    - "--output-format"
    - "stream-json"
    - "--include-partial-messages"
```

## Common mistakes

1. **Empty `capabilities_required`** — validation fails. Add at least
   one cap (usually `harness-run`).
2. **`sandbox.required: false`** — validation fails in v2. The whole
   point is to enforce sandbox; opt-out removed.
3. **Wildcard `args: ["*"]`** — would expand. Use specific args.
4. **Network `allow` without restriction** — only allow for
   authenticated CLIs; prefer `deny` for local models.
