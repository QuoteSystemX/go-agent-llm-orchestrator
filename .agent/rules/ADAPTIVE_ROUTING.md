---
trigger: always_on
---

# ADAPTIVE_ROUTING.md - Adaptive Delegation Protocol

This document defines the 4 levels of depth for request processing and the logic for automatic level transitions.

---

## 🟢 THE 4 LEVELS OF DEPTH

| Level | Name | Description | Active Units |
| :--- | :--- | :--- | :--- |
| **L1** | **Sprint (Спринт)** | Direct response from a single domain expert. | 1 Specialist Agent |
| **L2** | **Pro (Профи)** | Implementation with mandatory self-reflection/critique pass. | 1 Specialist + Self-Critic |
| **L3** | **Council (Совет Мудрецов)** | Synthetic consensus of multiple perspectives before action. | Architect + Specialist + SRE |
| **L4** | **Control (Красная Группа)** | Mission-critical audit with shadow review and security testing. | Red Team + Security + QA |

---

## 🤖 AUTOMATIC TRANSITION LOGIC (PRE-ANALYSIS)

Before any tool use, the system MUST perform an **Impact Scan** to determine the appropriate Flow.

### 1. Complexity Assessment

- **Score 1-3**: L1 (Sprint)
- **Score 4-6**: L2 (Pro)
- **Score 7-10**: L3 (Council)

### 2. Risk Assessment (The "Red Flag" check)

If any of these conditions are met, upgrade to **L4 (Control)**:

- Touches `production` environments.
- Modifies `authentication`, `security`, or `authorization` logic.
- Potential for high-impact data loss or system downtime.
- Involves complex Kubernetes infrastructure changes.

---

## 👥 SPECIALIZED GROUPS

### 🦉 Council of Sages (Совет Мудрецов)

Triggered for architectural decisions, complex migrations, or unclear requirements.

- **Goal**: Multidimensional planning.
- **Output**: Implementation Strategy or ADR.

### 🟥 Red Team (Красная Группа)

Triggered for high-risk operations or final security audits.

- **Goal**: Attack surface reduction and failure testing.
- **Output**: Audit Report and Hardening Recommendations.

---

## 🛠 FLOW CONSTRUCTION

The system will report the selected Flow at the start of every complex response:
`🤖 Flow: [L3 -> L2 -> L4]`

1. **Phase 1 (Strategy)**: Planning with L3.
2. **Phase 2 (Action)**: Implementation with L2.
3. **Phase 3 (Audit)**: Verification with L4.
