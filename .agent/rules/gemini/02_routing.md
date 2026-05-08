---
trigger: always_on
---

## 🤖 INTELLIGENT AGENT ROUTING (STEP 2 - AUTO)

**ALWAYS ACTIVE: Before responding to ANY request, automatically analyze and select the best agent(s) using Adaptive Routing.**

> 🔴 **MANDATORY:** You MUST follow the protocol defined in `@[skills/intelligent-routing]` and `.agent/rules/ADAPTIVE_ROUTING.md`.

### Auto-Selection Protocol

1. **Analyze (Silent)**: Detect domains and complexity.
2. **Build Flow**: Select Level (L1-L4) based on `.agent/rules/ADAPTIVE_ROUTING.md`.
3. **Inform User**: Concisely state the Flow at the start of EVERY response:
   - L1: `🤖 Flow: [L1]`
   - L2+: `🤖 Flow: [L3 -> L2]` (plus Model/History details)
4. **Apply**: Generate response using the selected levels and agents.
