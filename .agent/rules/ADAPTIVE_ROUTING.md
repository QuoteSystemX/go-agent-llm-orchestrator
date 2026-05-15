---
trigger: always_on
---

# ADAPTIVE_ROUTING.md - Adaptive Delegation Protocol

This document defines the 4 levels of depth for request processing and the logic for automatic level transitions.

---

## 🟢 THE 4 LEVELS OF DEPTH

| Level | Name | Description | Active Units |
| :--- | :--- | :--- | :--- |
| **L1** | **Sprint** | Direct response from a single domain expert. | 1 Specialist Agent |
| **L2** | **Pro** | Implementation with mandatory self-reflection/critique pass. | 1 Specialist + Self-Critic |
| **L3** | **Council of Sages** | Synthetic consensus of multiple perspectives before action. | Architect + Specialist + SRE |
| **L4** | **Red Team** | Mission-critical audit with shadow review and security testing. | Red Team + Security + QA |

> 💡 **Default Agent**: `orchestrator` is the primary system agent and is used as a "Fallback" if no specialist is defined or the task requires cross-domain management.
> 🔍 **Dynamic Discovery**: The system automatically finds agents by scanning the `.agent/agents/` folder and analyzing the `domains` field in their frontmatter. No static lists (agent_matrix.json) are required anymore.

---

## 🧭 DYNAMIC DISCOVERY PROTOCOL

The Auctioneer (`agent_auctioneer.py`) works according to the following algorithm:

1. **Scan**: Traverse all `.md` files in `.agent/agents/`.
2. **Extract**: Parse Frontmatter to extract `domains` and `skills`.
3. **Match**: Calculate Score based on domain keywords present in the task description.
4. **Identity Match**: If the agent ID (filename) is mentioned in the task, it receives priority (+2 to Score).

---

## 🤖 AUTOMATIC TRANSITION LOGIC (PRE-ANALYSIS)

Before any tool use, the system MUST perform an **Impact Scan** to determine the appropriate Flow.

### 1. Complexity Assessment

- **Score 1-3**: L1 (Sprint)
- **Score 4-6**: L2 (Pro)
- **Score 7-9**: L3 (Council)
- **Score 10+**: L4 (Control)

### 2. Risk Assessment (The "Red Flag" check)

If any of these conditions are met, upgrade to **L4 (Control)**:

- Touches `production` environments.
- Modifies `authentication`, `security`, or `authorization` logic.
- Potential for high-impact data loss or system downtime.
- Involves complex Kubernetes infrastructure changes.

---

## 👥 SPECIALIZED GROUPS

### 🦉 Council of Sages

Triggered for architectural decisions, complex migrations, or unclear requirements.

- **Goal**: Multidimensional planning.
- **Output**: Implementation Strategy or ADR.

### 🟥 Red Team

Triggered for high-risk operations or final security audits.

- **Goal**: Attack surface reduction and failure testing.
- **Output**: Audit Report and Hardening Recommendations.

---

## 🛠 FLOW CONSTRUCTION

The system will report the selected Flow at the start of every response:

- **L1 (Sprint)**: `🤖 Flow: [L1]`
- **Complex (L2-L4)**: `🤖 Flow: [L3 -> L2 -> L4]` (including Model and History metadata)

1. **Phase 1 (Strategy)**: Planning with L3.
2. **Phase 2 (Action)**: Implementation with L2.
3. **Phase 3 (Audit)**: Verification with L4.

---

## 🎯 SKILL ROUTING PROTOCOL

When a task involves a domain with multiple specialized skills, use the **router skill** first.

### How It Works

```text
Task: "build API for user management"
    │
    └── Detect domain: API Development
            │
            └── Use router: @[skills/api-development]
                    │
                    ├── Determine stack (go.mod → Go)
                    ├── Route to: @[skills/go-patterns]
                    ├── Apply security: @[skills/vulnerability-scanner]
                    └── Generate contracts: @[skills/typed-service-contracts]
```

### Router Skills Registry

| Domain | Router Skill | Children |
| :--- | :--- | :--- |
| **API Development** | `api-development` | api-patterns, nodejs/python/go/rust, security, contracts |
| **Frontend** | `frontend-development` (future) | frontend-design, nextjs, mobile-design, ui-ux-pro-max |
| **Backend** | `backend-development` (future) | api-development, nodejs/python/go, database-design |

### When to Use Router Skills

1. **Task mentions general domain**: "build API", "build UI", "build backend"
2. **Multiple skills could apply**: Check router skill's routing matrix
3. **Unclear which specific skill**: Router skill determines based on context

### Rule

> 🔴 **If >3 related skills exist for a domain, there MUST be a router skill.**
> When creating new skills, check if a router skill needs updating.

### Enforcement

Router skills are documented in `LESSONS_LEARNED.md` under "Skill Router Registry".
Run `python3 .agent/scripts/knowledge/experience_distiller.py --skill intelligent-routing` to see current routers.
