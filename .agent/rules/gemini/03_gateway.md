# Output Gateway Protocol

---
trigger: always_on
---

## 📤 OUTPUT GATEWAY (MANDATORY)

**Every response that involves code changes, features, or complex logic MUST be validated via `bin/output-bridge`.**

1. **Format**: Follow the structure: Header, Goal, Implementation, Components, Result.
2. **Validation**: Run `cat response.md | bin/output-bridge`.
3. **Strict Mode**: Responses that fail gateway validation are REJECTED and must be corrected.

### 🧠 HYBRID ROUTING PROTOCOL (MANDATORY - ENFORCED)

**Before executing ANY sub-task or delegation, the agent MUST:**

1. **Call the Router**: Run `python3 .agent/scripts/models/model_router.py "<task_description>" --json`.
2. **Respect the Decision**:
   - If `provider == "ollama"`, use `ollama_agent.py` with local models.
   - If `provider == "antigravity"`, use built-in cloud agents (fallback only).
3. **Context Bus Check**: Check `.agent/bus/` for recent `routing_event` objects.

### 🔴 ENFORCEMENT: Ollama is PRIMARY, Cloud is FALLBACK only

```bash
# CORRECT workflow for ANY Ollama task:
python3 .agent/scripts/models/model_router.py "task description" --json
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

Every response MUST start with the following header (replace placeholders with real values):


```text
🤖 Flow: **[L<N>]**
🧠 Team Consensus: **[Brief summary of consensus]**
👤 Agent: **@agent-name** | 🛠 Skills: **[skill-1, skill-2]** | 📈 Health: **<score>%** | 🛡️ Sentinel: **ACTIVE/OFF**
```
**Mandatory Content Structure:**

- 🎯 **Context/Goal**: Brief description
- 🛠 **Technical Implementation**: Technical details
- 📂 **Impacted Components**: Absolute file paths
- 📈 **Outcome/Result**: Verification status

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
