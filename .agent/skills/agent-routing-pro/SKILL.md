---
name: agent-routing-pro
description: Advanced adaptive routing implementation with 4 levels of depth and preliminary analysis.
version: 1.0.0
---

# Agent Routing Pro

This skill implements the **Adaptive Delegation Protocol** as defined in `.agent/rules/ADAPTIVE_ROUTING.md`.

## 🔄 Preliminary Analysis Workflow

Before performing any task, the system MUST follow this preliminary analysis:

### 0. Task Tree Decomposition (L3/L4 Only)
For complex tasks, build a **Dynamic Task Tree**:
1. **Root**: Main Objective.
2. **Branches**: Major domains (e.g., Backend, Infra, UI).
3. **Nodes**: Atomic sub-tasks.
**Visual**: Produce a mermaid diagram of the tree in the Strategy phase.

### 1. Classification (Impact Scan)
**Step 0: Experience Search (MANDATORY)**
Run `python3 .agent/scripts/experience_distiller.py --query "task keywords"`.
- If relevant lessons exist -> Note them in the report.
- If a lesson indicates a high risk or past failure in this area -> Escalate Level (e.g., L2 -> L3).

**Step 1: Model Selection (MANDATORY)**
Run `python3 .agent/scripts/model_router.py "[Task Description]"` to select the model tier.
- **L1 Task** -> Uses Flash/Haiku.
- **L3/L4 Task** -> Uses Pro/Sonnet/Opus.
- Inject the selected model into the response header.

**Step 2: Tool Assignment (MCP)**
Assign specialized tools based on the task domain:
- `shadcn` for UI.
- `browser` for documentation or web audits.
- `wikipedia` for research.
- `github` for repository analysis.

**Step 1: Complexity & Risk Detection**
Analyze the request to determine complexity and risk.
- **Is it a simple fix?** -> L1
- **Does it require logic changes?** -> L2
- **Is it an architectural decision?** -> L3 (Council of Sages)
- **Is it high-risk (prod, security, k8s)?** -> L4 (Red Team)

### 2. Failure Detection (Escalation Trigger)
Check previous conversation turns for keywords: "error", "fail", "not working".
If a failure is detected in a recent L1/L2 response, escalate the current Flow by +1 level.

### 3. Flow Construction
Build the execution sequence.
- **Example 1**: Simple bug fix -> `🤖 Flow: [L1]`
- **Example 2**: New feature -> `🤖 Flow: [L3 -> L2]`
- **Example 3**: Prod DB migration -> `🤖 Flow: [L3 -> L2 -> L4]`

### 3. Reporting (Memory-Augmented)
Every response MUST start with:
`🤖 Flow: [Levels]`
`🧠 Model: [Provider] -> [Selected Model]`
`📈 History: [Summary of found lessons or "None"]`

---

## 👥 Group Definitions

### 🦉 Council of Sages (Совет Мудрецов)
- **Activation**: L3 Tasks.
- **Composition**: `architect` + `domain-specialist` + `sre-engineer`.
- **Mode**: Synthetic Consensus (All 3 perspectives in one response).

### 🟥 Red Team (Красная Группа)
- **Activation**: L4 Tasks.
- **Composition**: `red-team` + `security-auditor`.
- **Mode**: Shadow Review (Critical audit after implementation).

---

## 🛠 Multi-Level Execution Rules

### L2 (Pro) - Self-Correction Protocol
- Step 1: Implement the task.
- Step 2: (Internal) Switch to "Critic" persona.
- Step 3: Find 3 potential flaws or optimizations.
- Step 4: Apply fixes before final output.

### L3 (Council) - Consensus Protocol
- **Step 1: Task Tree**: Decompose objective into a hierarchical task tree.
- **Step 2: Multi-Expert Review**: Present 3 distinct perspectives on the tree branches.
- **Step 3: Conflict Detection**: Compare perspectives for contradictions.
- **Step 4: Unified Path**: Finalize the tree with specific implementation nodes.
- **Mandatory**: Include mermaid diagram and `## 🧠 Internal Discussion Log`.

### L4 (Control) - Audit Protocol
- Step 1: Pass through L3 and L2.
- Step 2: Red Team attempts to "break" the proposed solution.
- Step 3: **Conflict Detection**: Verify if Red Team fixes introduce new architectural regressions.
- Step 4: Final hardening pass.
- **Mandatory**: Include `## 🧠 Internal Discussion Log` section with Red Team insights and `⚔️ Conflicts`.
