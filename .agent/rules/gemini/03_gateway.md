---
trigger: always_on
---

## 📤 OUTPUT GATEWAY (MANDATORY)

**Every response that involves code changes, features, or complex logic MUST be validated via `bin/output-bridge`.**

1.  **Format**: Follow the structure: Header, Goal, Implementation, Components, Result.
2.  **Validation**: Run `cat response.md | bin/output-bridge`.
3.  **Strict Mode**: Responses that fail gateway validation are REJECTED and must be corrected.

### 🧠 HYBRID ROUTING PROTOCOL (MANDATORY)

**Before executing ANY sub-task or delegation, the agent MUST:**

1. **Call the Router**: Run `python3 .agent/scripts/model_router.py "<task_description>" --json`.
2. **Respect the Decision**: 
   - If `provider == "ollama"`, use local models via MCP/Ollama.
   - If `provider == "antigravity"`, stay in cloud.
3. **Context Bus Check**: Check `.agent/bus/` for recent `routing_event` objects to maintain consistency across the session.

*Rationale: This ensures optimal cost/performance balance and enables the self-learning loop via router_trainer.py.*

---

**Mandatory Structure:**
- 🤖 **Agent Header**: specialist-name
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
|------|-------|--------------|
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
