# Go MCP LLM Broker & Gateway

A stateless, keyless, workspace-aware Go binary that acts as a unified LLM gateway.
Runs in **dual mode** — MCP-over-Stdio for IDE integration + optional HTTP REST API.

---

## Features

- **Multi-Backend Provider Detection**: Automatically discovers and monitors:
  - **Ollama** (native `/api/generate`)
  - **Jan** (OpenAI-compatible `/v1/chat/completions`)
  - **LM Studio** (OpenAI-compatible `/v1/chat/completions`)
- **Smart Model Routing**: Scores prompt complexity (1–18), maps to tiers (L1–L4), matches against **all available models** across detected backends.
- **Cloud Fallback**: Unknown models or high-tier tasks auto-routed to cloud provider (`antigravity`), never falling through to a dead local backend.
- **Dual Mode**:
  - **MCP Mode** — Stdio-based MCP server for AI agent tool calls
  - **HTTP Mode** — OpenAI-compatible REST API (`/v1/chat/completions`, `/v1/models`, `/healthz`)
- **Built-in Middlewares**:
  - **Caching**: In-memory + file-based under `.agent/tmp/llm_cache/`
  - **Token Saver**: Strips duplicate whitespace and redundant instructions
- **Environment-Aware**: Auto-detects WSL (routes to Windows Ollama via gateway) and K8s
- **No API Keys Required**: Local models are free; cloud fallback uses headroom proxy without storing credentials

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    mcp-llm-broker                        │
│                                                          │
│  ┌─────────────────┐     ┌──────────────────────────┐   │
│  │   MCP Server     │     │    HTTP Server (opt)     │   │
│  │   (Stdio)        │     │    :<port>               │   │
│  │                  │     │                          │   │
│  │  detect_backends │     │  GET /healthz            │   │
│  │  get_routing_dec │     │  GET /v1/models          │   │
│  │  execute_prompt  │     │  POST /v1/chat/completions│   │
│  └─────────────────┘     └──────────────────────────┘   │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │           Shared Execution Engine                  │   │
│  │  ┌──────────┐  ┌──────────┐  ┌────────────────┐  │   │
│  │  │  Ollama   │  │   Jan    │  │   LM Studio    │  │   │
│  │  │:11434/api │  │:1337/v1  │  │:1234/v1        │  │   │
│  │  └──────────┘  └──────────┘  └────────────────┘  │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

## Provider Detection Logic

On startup and every 20s thereafter, the broker polls all three local backends:

| Provider  | Detection Method         | Health URL              | Execution URL                    |
|-----------|--------------------------|-------------------------|----------------------------------|
| Ollama    | `GET /api/tags`          | `:11434/api/tags`       | `:11434/api/generate`            |
| Jan       | `GET /v1/models`         | `:1337/v1/models`       | `:1337/v1/chat/completions`      |
| LM Studio | `GET /v1/models`         | `:1234/v1/models`       | `:1234/v1/chat/completions`      |

- **Available models** from all backends are merged into a single pool for routing.
- **Unavailable backends** are skipped (no crash, no timeout stall).
- **Model name matching** uses loose comparison (strips size suffixes, normalizes tags).

---

## MCP Tools (Stdio Mode)

### 1. `detect_backends`
Probes all local providers + WSL/K8s environment.

```json
{
  "environment": { "os": "darwin", "is_wsl": false, "is_k8s": false },
  "backends": [
    { "name": "Ollama", "url": "http://localhost:11434", "available": false, "error": "connection refused" },
    { "name": "Jan",    "url": "http://localhost:1337",  "available": true,
      "models": ["Jan-v3.5-4B-Q4_K_XL", "DeepSeek-R1-0528-Qwen3-8B-IQ4_XS"] },
    { "name": "LM Studio", "url": "http://localhost:1234", "available": false }
  ]
}
```

### 2. `get_routing_decision`
Analyzes task complexity, returns best model + provider.

| Argument          | Type   | Required | Description                           |
|-------------------|--------|----------|---------------------------------------|
| `task_description`| string | ✅       | The task to analyze                   |

### 3. `execute_prompt`
Routes prompt to the optimal backend, runs preprocessing, checks cache, executes LLM.

| Argument          | Type   | Required | Description                           |
|-------------------|--------|----------|---------------------------------------|
| `prompt`          | string | ✅       | The prompt to send                    |
| `system_prompt`   | string | ❌       | System instructions                   |
| `difficulty_hint` | string | ❌       | Complexity hint (overrides auto-detect)|
| `model`           | string | ❌       | Model override (skips routing)        |
| `json_schema`     | string | ❌       | JSON Schema for structured output     |
| `stream`          | string | ❌       | `"true"` for streaming                |

### 4. `call_agent`
Loads a specialist agent's system prompt from `.claude/agents/<name>.md` and executes the task under that persona. Used by the agentic loop (see below) and available as a direct MCP tool for orchestrators.

| Argument     | Type   | Required | Description                                   |
|--------------|--------|----------|-----------------------------------------------|
| `agent_name` | string | ✅       | Exact name from the agent list (never `orchestrator`) |
| `task`       | string | ✅       | Task or question to send to the agent         |
| `tier`       | string | ❌       | Override routing tier: `L1`, `L2`, `L3`, `L4` |

Agent tiers are auto-resolved from `agent_tiers` in `router_rules.json` if not specified.

---

## Agentic Loop (Orchestrator Mode)

When the system prompt contains orchestrator keywords (`orchestrator`, `multi-agent`, `call_agent`, `delegate`, `sub-agent`, etc.), the broker automatically switches from single-shot LLM calls to a **multi-turn agentic loop**:

```
User prompt
    │
    ▼
Jan (Qwen3-27B @ L3) ──── call_agent tool definition injected ────►
    │
    ├── tool_use: call_agent(agent_name="debugger", task="...")
    │       │
    │       └─► invokeAgent("debugger") → executePromptLogic (L2 tier)
    │               └─► Jan (DeepSeek-8B) → result text
    │
    ├── tool_result fed back to Jan
    │
    └── Jan synthesizes final answer → returned to caller
```

### Loop parameters

| Parameter | Value | Reason |
|-----------|-------|--------|
| Max iterations | **10** | Supports chains of up to 8 agent calls + 1 planning turn + 1 synthesis turn. More than 10 usually indicates the model is stuck in a loop. |
| Semaphore scope | **per-iteration** | Released before each sub-agent call so the sub-agent can acquire the same Jan slot without deadlocking. |
| Schema mode | **disabled** | `json_schema` is incompatible with the agentic loop (single-shot mode used instead). |

### Context overflow handling

If Jan returns `exceed_context_size_error` (prompt + output > model's `n_ctx`):
1. Broker parses `n_ctx` and `n_prompt_tokens` from the error response.
2. Trims the system prompt by the excess token count, cutting at a `\n` boundary.
3. Reduces `max_tokens` to `n_ctx / 4` to leave 75% of context for input.
4. Retries the same iteration automatically (one retry per iteration maximum).

This handles the common case where an agent's system prompt file is large but the loaded model has a smaller context window than expected.

---

## HTTP REST API (OpenAI-Compatible)

Start with `--http-port`:

```bash
./mcp-llm-broker --http-port 11436
```

### `GET /healthz`

```json
{
  "status": "ok",
  "version": "1.0.0",
  "backends": {
    "ollama": false,
    "jan": true,
    "lm-studio": false
  }
}
```

### `GET /v1/models`

Returns all models from **all active backends**, tagged with `owned_by`:

```json
{
  "object": "list",
  "data": [
    { "id": "DeepSeek-R1-0528-Qwen3-8B-IQ4_XS", "object": "model", "owned_by": "jan" },
    { "id": "Jan-v3.5-4B-Q4_K_XL",               "object": "model", "owned_by": "jan" }
  ]
}
```

### `POST /v1/chat/completions`

Fully OpenAI-compatible request/response. Supports:

- **Auto-routing** (no `model` field) — selects best local model
- **Model override** (`model: "Jan-v3.5-4B-Q4_K_XL"`) — routes to that specific model
- **Unknown models** (`model: "gpt-4o"`) — routes to cloud fallback provider
- **Streaming** (`stream: true`) — SSE server-sent events
- **CORS** — enabled on all endpoints

#### Request

```json
{
  "model": "Jan-v3.5-4B-Q4_K_XL",
  "messages": [
    { "role": "system", "content": "You are a helpful assistant." },
    { "role": "user", "content": "Say hello in 3 words." }
  ],
  "stream": false
}
```

#### Response

```json
{
  "id": "chatcmpl-1749600000000000001",
  "object": "chat.completion",
  "created": 1749600000,
  "model": "Jan-v3.5-4B-Q4_K_XL",
  "choices": [{
    "index": 0,
    "message": { "role": "assistant", "content": "Hello there!" },
    "finish_reason": "stop"
  }],
  "usage": { "prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15 }
}
```

---

## Cloud Fallback Behavior

When a model is **not found** on any local backend, the broker routes to the cloud fallback provider (`antigravity` by default).

| Scenario                          | Before Fix (v1.0)                 | Now (v1.1)                        |
|-----------------------------------|-----------------------------------|-----------------------------------|
| Unknown model (`gpt-4o`)          | Tried dead Ollama (`:11434`)      | Routes to `api.antigravity.io`    |
| All backends down                 | Fell through to localhost Ollama  | Returns clear error with URL      |
| `/v1/models` with Ollama down     | Showed only Ollama error          | Shows models from Jan/LM Studio   |

---

## Streaming & Response Cleanup

### Direct Jan Streaming (`tryStreamDirect`)

When `stream: true` is set in a chat request and Jan is the selected backend, the broker
opens a **direct SSE connection** to Jan instead of buffering the full response. Tokens are
forwarded to the client as they arrive, with the `thinkFilter` stripping thinking content
in real-time (see below).

If Jan is unreachable or routing selects a cloud provider, the broker automatically falls
back to the standard buffered `executePromptLogic` path — the client sees no difference.

### Think Block Filtering

Several local reasoning models (DeepSeek R1, Qwen3, Gemma 3) emit internal reasoning inside
`<think>...</think>` tags before their visible answer.

- **Streaming responses** — `thinkFilter` strips thinking tokens on-the-fly with a 6-rune
  lookahead buffer to handle tags that arrive split across chunk boundaries. Multibyte UTF-8
  characters (e.g. Cyrillic) are never split between output and buffer.
- **Buffered responses** — `stripThinkBlocks` removes complete and unclosed `<think>` blocks
  from the final string before returning the result.

### DeepSeek R1 Special Token Cleanup

DeepSeek R1 (and R1-distill) models emit proprietary Unicode tokens used by their native
tool-call format. When these tokens appear in broker responses (where tool parsing is not
implemented for this format), `stripThinkBlocks` removes everything from the first marker
to end-of-string:

```
<｜tool▁outputs▁begin｜>  <｜tool▁output▁begin｜>  <｜tool▁outputs▁end｜>
<｜tool▁call▁begin｜>     <｜tool▁call▁end｜>       <｜tool▁sep｜>
<｜fim▁begin｜>           <｜fim▁hole｜>             <｜fim▁end｜>
```

---

## CLI Mode (Direct Execution)

```bash
# Detect active backends
./bin/mcp-llm-broker -tool detect_backends

# Get a routing decision
./bin/mcp-llm-broker -tool get_routing_decision \
  -args '{"task_description": "fix zero-day exploit in auth logic"}'

# Execute a prompt with JSON schema
./bin/mcp-llm-broker -tool execute_prompt \
  -args '{"prompt": "Extract name: John Doe, age 30", "json_schema": "{\"type\":\"object\",\"properties\":{\"name\":{\"type\":\"string\"},\"age\":{\"type\":\"number\"}}}"}'
```

---

## Jan Model Configuration (RTX 4090 24 GB)

Recommended `n_ctx` values per model. KV cache grows linearly with context — pushing 128K on a 27B+ dense model exhausts VRAM before the model itself fits.

| Model | Tier | Recommended n_ctx | Notes |
|-------|------|-------------------|-------|
| `Jan-v3.5-4B-Q4_K_XL` | L1 | **8 192** | Small model — big context wastes VRAM with no quality gain |
| `DeepSeek-R1-0528-Qwen3-8B-IQ4_XS` | L2 | **65 536** | Trained for long context; KV ~5 GB at 64K → fits easily |
| `gemma-4-12B-it-UD-IQ4_XS` | L2/L3 | **65 536** | KV ~6 GB at 64K + ~7 GB weights ≈ 13 GB total |
| `gemma-4-26B-A4B-it-UD-IQ4_XS` | L3 | **32 768** | MoE but attention is dense; KV ~10 GB at 32K + ~15 GB weights |
| `Qwen3_6-27B-*` | L3 | **32 768** | Dense 27B; KV ~12 GB at 32K + ~15 GB weights → ~27 GB at 64K OOM |
| `Qwen3_6-35B-A3B-*` | L3/L4 | **32 768** | MoE; attention overhead still large; 64K risks OOM |

### Why not 128K for everything?

KV cache formula: `2 × layers × kv_heads × head_dim × n_ctx × 2 bytes`

| Model | KV @ 32K | KV @ 64K | KV @ 128K |
|-------|----------|----------|-----------|
| 8B (DeepSeek) | ~2.5 GB | ~5 GB | ~10 GB ✅ |
| 12B (Gemma) | ~3 GB | ~6 GB | ~12 GB ✅ |
| 26B MoE (Gemma) | ~5 GB | ~10 GB | ~20 GB ⚠️ |
| 27B dense (Qwen3) | ~6 GB | ~12 GB | ~24 GB ❌ OOM |
| 35B MoE (Qwen3) | ~8 GB | ~15 GB | ~30 GB ❌ OOM |

`router_rules.json` already sets `"n_ctx": 131072` for the broker's internal awareness — Jan/Ollama use their own per-model setting. Set the values above in Jan's model settings UI.

---

## Configuration

All configuration is workspace-relative, read from `.agent/`:

| File                          | Purpose                                       |
|-------------------------------|-----------------------------------------------|
| `.agent/config/router_rules.json` | Routing weights, tiers, model rankings     |
| `.agent/config/watchdog_rules.json` | Token budgets, execution limits         |
| `.agent/rules/LESSONS_LEARNED.md` | Historical failure contexts for scoring   |
| `.agent/bus/telemetry.json`   | Execution latency, token usage                |

---

## Building

### Prerequisites
- Go 1.22+

### Commands

```bash
make deps       # Download + tidy
make build      # Current platform (fast dev)
make build-darwin  # macOS universal fat binary
make build-linux   # Linux amd64
make all        # Build all platforms
```

Output goes to `bin/`. The launcher script `mcp-llm-broker.sh` auto-selects the right binary for the platform.

### Running

```bash
# MCP Stdio mode (default)
./bin/mcp-llm-broker

# HTTP mode (with MCP still active on Stdio)
./bin/mcp-llm-broker --http-port 11436

# CLI mode (execute once and exit)
./bin/mcp-llm-broker -tool detect_backends

# Custom workspace
./bin/mcp-llm-broker --workspace /path/to/project
```

## Routing Test Cases

Score formula: `base(5) + keyword_weights`. Thresholds: `L1 ≤ 3`, `L2 ≤ 7`, `L3 ≤ 10`, `L4 > 10`.

> Note: L1 is auto-bumped to L2 when system prompt > 500 chars (orchestrator context).
> Non-complex queries use `tool_choice: auto`; complex queries force `call_agent` on iter 0.

### L1 — score ≤ 3 (negative weights required)

| Prompt | Score calc | `isComplex` | Expected |
|--------|-----------|-------------|---------|
| `обнови readme` | 5 − 5(readme) = **0** | false | Jan-4B → bumped L2, auto, 1 iter |
| `исправь typo` | 5 + 3(исправ) − 5(typo) = **3** | true | Jan-4B, call_agent |
| `check readme typo` | 5 − 5(readme) − 5(typo) + 3 = **−2** | false | Jan-4B, auto |

### L2 — score 4–7 (conversational / non-technical)

| Prompt | Score calc | `isComplex` | Expected |
|--------|-----------|-------------|---------|
| `привет` | **5** | false | DeepSeek-8B, auto, direct reply, ~4 s |
| `как дела?` | **5** | false | DeepSeek-8B, auto, direct reply |
| `расскажи о проекте` | **5** | false | DeepSeek-8B, auto |
| `update documentation` | 5 + 2(documentation) = **7** | false | DeepSeek-8B, auto |

### L3 — score 8–10 (technical tasks, delegates)

| Prompt | Score calc | `isComplex` | Expected |
|--------|-----------|-------------|---------|
| `реализуй новый endpoint` | 5 + 4(реализуй) = **9** | true | Qwen-27B, call_agent, streaming |
| `рефактор модуля` | 5 + 5(рефактор) = **10** | true | Qwen-27B, call_agent, streaming |
| `анализ кода` | 5 + 5(анализ) = **10** | true | Qwen-27B → explorer-agent, streaming |
| `implement feature` | 5 + 4(implement) = **9** | true | Qwen-27B, call_agent |

### L4 — score > 10 (security / architecture)

| Prompt | Score calc | `isComplex` | Expected |
|--------|-----------|-------------|---------|
| `можешь сделать дебаг?` | 5 + 5(дебаг) + 3(сделай) = **13** | true | L4 model, call_agent |
| `исправь ошибку` | 5 + 3(исправ) + 3(ошибк) = **11** | true | L4 model |
| `security audit` | 5 + 7(security) + 6(audit) = **18** | true | L4 model |
| `анализ безопасности` | 5 + 5(анализ) + 7(безопасност) = **17** | true | L4 model |
| `рефактор архитектуры` | 5 + 5(рефактор) + 9(архитектур) = **19** | true | L4 model |

### Performance stats format

Response footer: `19 tok/s (742 tokens) · score=10 L3 · Qwen3_6-27B-IQ4_XS`

- **tok/s** = orchestrator model tokens ÷ wall-clock time (includes sub-agent wait)
- **tokens** = only orchestrator model output tokens; sub-agent tokens not counted
- Lower tok/s on multi-agent tasks is expected — time includes sub-agent roundtrips
