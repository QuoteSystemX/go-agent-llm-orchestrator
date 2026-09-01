# Output Gateway Protocol

---
trigger: always_on
---

## 📤 OUTPUT GATEWAY (MANDATORY)

**Every response that involves code changes, features, or complex logic MUST be validated via `bin/output-bridge`.**

1. **Format**: Follow the structure: Header, Goal, Implementation, Components, Result.
2. **Validation**: Run `cat .agent/tmp/response.md | bin/output-bridge` (or pipe the response string directly).
3. **Strict Mode**: Responses that fail gateway validation are REJECTED and must be corrected.

### 🧠 HYBRID ROUTING PROTOCOL (MANDATORY - ENFORCED)

**Before executing ANY sub-task or delegation, the agent MUST:**

1. **Call the Router**: Run `./bin/mcp-llm-broker -tool get_routing_decision -args '{"task_description": "<task_description>"}'`.
2. **Respect the Decision**:
   - If `provider == "ollama"`, use `ollama_agent.py` with local models.
   - If `provider == "antigravity"`, use built-in cloud agents (fallback only).
3. **Context Bus Check**: Check `.agent/bus/` for recent `routing_event` objects.

### 🔴 ENFORCEMENT: Ollama is PRIMARY, Cloud is FALLBACK only

```bash
# CORRECT workflow for ANY Ollama task:
./bin/mcp-llm-broker -tool get_routing_decision -args '{"task_description": "task description"}'
# → Response: {"provider": "ollama", "model_id": "qwen3-coder:30b", "tier": "L4"}

# Use ollama_agent.py for filesystem-aware analysis:
python3 .agent/scripts/models/ollama_agent.py "analyze technical debt" --agent code-archaeologist --model qwen3-coder:30b

# WRONG (violation): Using built-in cloud agents when Ollama available
```

**WSL Support**: Router auto-detects WSL via `_is_wsl()` and routes to Windows Ollama at `172.31.0.1:11434`.

**Required Logging**:

```text
🤖 Flow: [L<N>]
🧠 Provider: Ollama (WSL auto-detected)
🧠 Model: <model_id>
🧠 Score: <score>/18
✅ Cost saved vs cloud
```

**No fabricated values**: every field above must be copied verbatim from the JSON the router
command actually returned this turn (`provider`, `model_id`, `score`). If the router was not
called, or the call failed, do not guess a plausible-looking value — write `unknown` instead.
A wrong-but-confident model name is worse than an honest `unknown`; both `output_bridge.py` and
downstream automation now treat a confidently wrong self-report as a hallucination, not `unknown`.

**Benchmark Results (2026-05-10, simple/medium/complex tasks)**:

| Tier | Best Model | Avg Time | Avg TPS | Success |
| :--- | :--- | :--- | :--- | :--- |
| L1 | codestral:22b | 7.4s | 39 tok/s | 100% |
| L2 | qwen2.5-coder:14b | **6.4s** | **61 tok/s** | 100% |
| L3 | qwen2.5-coder:32b | 13.6s | 28 tok/s | 100% |
| L4 | qwen3-coder:30b | **3.6s** | **129 tok/s** | 100% |
| L4-alt | qwen3.6:27b | 53.8s | 8 tok/s | 100% |

*Rationale: This ensures optimal cost/performance balance via ollama_agent.py with filesystem context.*

### 🧠 IDENTITY HEADER PROTOCOL (MANDATORY)

Every response MUST start with the following header:

```text
🤖 Flow: **[L<N>]** | 🔄 **Process**: <sequence>
🧠 Team Consensus: **[Brief summary]** | 👤 Agent: **@agent-name** | 🛡️ **Sentinel**: **ACTIVE/OFF**
```

**`Sentinel` is not a vibe — it reports whether `governance_gate.py` (the actual Sentinel
Governance Gate, `.agent/scripts/orchestration/governance_gate.py`) was run against the impacted
files this turn and what it returned.** Write `ACTIVE` only if you actually ran it (directly, or
via the orchestrator) and it passed; write `OFF` if you did not run it, or ran it and it failed.
`OFF` is the safe default — same principle as `unknown` for Model above: an honest "I didn't check"
beats a confidently wrong "ACTIVE" that was never verified.

**`TPS` / `Tokens` / `Model` / `Health` are NOT self-reported.** You do not have reliable access to
your own model identity, token counts, or throughput — do not fabricate them. Two cases:

1. **Running through `mcp-llm-broker`'s `call_agent`** (this is how you were most likely invoked):
   the broker stamps the *verified* `model_used`, `provider`, and `is_cloud` fields on the JSON
   envelope around your response, from its own routing decision — not from anything you write.
   Do not include `TPS`/`Tokens`/`Model`/`Health` in your header at all; they would only duplicate
   or contradict the broker's verified fields.
2. **Any other invocation path** (no broker stamping available): if you genuinely have real
   numbers from an actual tool call this turn (e.g. `get_routing_decision`), copy them verbatim.
   Otherwise write `Model: unknown` / `TPS: unknown` — never a specific-but-invented name or
   number. This was a real, confirmed failure mode: local models were observed either copying the
   static example row from this file's own benchmark table verbatim and presenting it as live
   telemetry, or inventing a plausible-but-wrong number — both are worse than admitting `unknown`.

*Note: The `RTK` metrics field is optional but highly recommended when context compression is enabled to track real-time resource and token savings — same rule applies: real measured values or `unknown`, never invented.*

**Mandatory Content Structure (Premium Standard):**

- 🎯 **Context/Goal**: Brief description.
- 🛠 **Technical Implementation**: Technical details.
- 📂 **Impacted Components**: Clickable file links using `[basename](file:///path/to/file)`.
- 📈 **Outcome/Result**: Verification status with checkboxes and metrics.
- 🧠 **Lesson of the Turn**: (Optional but Recommended) A single sentence on what the agent learned or a key insight.

**Rules:**

1. **Silent Analysis**: No verbose meta-commentary ("I am analyzing...").
2. **Respect Overrides**: If user mentions `@agent`, use it.
3. **Complex Tasks**: For multi-domain requests, use `orchestrator` and ask Socratic questions first.

### ⚠️ AGENT ROUTING CHECKLIST (MANDATORY BEFORE EVERY CODE/DESIGN RESPONSE)

**Before ANY code or design work, you MUST complete this mental checklist:**

| Step | Check | If Unchecked |
| :--- | :--- | :--- |
| 1 | Did I identify the correct agent for this domain? | → STOP. Analyze request domain first. |
| 2 | Did I READ the agent's `.md` file (or recall its rules)? | → STOP. Open `.agent/agents/{agent}.md` |
| 3 | Did I announce `🤖 Applying knowledge of @[agent]...`? | → STOP. Add announcement before response. |
| 4 | Did I load required skills from agent's frontmatter? | → STOP. Check `skills:` field and read them. |

**Failure Conditions:**

- ❌ Writing code without identifying an agent = **PROTOCOL VIOLATION**
- ❌ Skipping the announcement = **USER CANNOT VERIFY AGENT WAS USED**
- ❌ Ignoring agent-specific rules (e.g., Purple Ban) = **QUALITY FAILURE**

> 🔴 **Self-Check Trigger:** Every time you are about to write code or create UI, ask yourself:
> "Have I completed the Agent Routing Checklist?" If NO → Complete it first.
