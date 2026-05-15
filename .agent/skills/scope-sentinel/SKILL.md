---
name: scope-sentinel
description: Mid-session scope drift detector and self-escalation protocol for specialist agents. Prevents "Sticky Context Bias" by checking each incoming question against the agent's domain boundary and escalating to orchestrator when scope expands.
version: 1.0.0
---

# Scope Sentinel — Self-Escalation Protocol

**Purpose**: Prevent specialist agents from answering questions outside their domain ("Sticky Context Bias"). Applied per-turn, before any response.

---

## 🔴 MANDATORY PER-TURN CHECK

**Before answering ANY question, every specialist agent MUST run this check silently:**

```
SCOPE_CHECK(current_question, my_domain):

  1. Does the question mention other repos/services?
     → SIGNALS: "neighboring repos", "other services", "compare repos",
                "across all charts", "in other projects", "cross-service",
                "consistency across", "other services", "neighboring repos"
     → ACTION: ESCALATE to orchestrator

  2. Does the question require knowledge of 2+ domains NOT in my domain list?
     → Example: k8s-engineer receives question about DB schema + Ingress + CI/CD
     → ACTION: ESCALATE to orchestrator

  3. Does the question ask for cross-repo consistency audit?
     → SIGNALS: "check how it is configured in others", "compare with neighbors",
                "is it the same everywhere", "consistency check", "audit across"
     → ACTION: ESCALATE to orchestrator

  4. Does the question involve architectural decisions spanning multiple services?
     → SIGNALS: "architectural decision", "architectural decision", "ADR",
                "system-wide", "across the entire system", "global policy"
     → ACTION: ESCALATE to orchestrator (Council of Sages may be needed)

  5. None of the above? → PROCEED with answering as normal
```

---

## Escalation Response Format

When scope drift is detected, do NOT attempt to answer. Respond with:

```markdown
🔄 **Scope escalation triggered** — this question crosses into cross-service / cross-repo territory,
which is beyond a single specialist's view.

**Detected signal**: [quote the phrase that triggered escalation]
**My domain**: [your agent domain]
**Required scope**: [what domains are actually needed]

Handing off to `@orchestrator` for coordinated analysis.

> **For the orchestrator**: User is asking [restate the question clearly]. 
> Relevant specialists: [list agents by domain]. Context so far: [1-2 sentence summary].
```

---

## Domain Boundary Reference

Each specialist knows their own boundary. If a question is at the boundary (could be either domain), apply the **narrower domain wins** rule: escalate rather than risk scope creep.

| If you are... | Your domain stops at... |
|--------------|------------------------|
| `backend-specialist` | One service's API/DB. Cross-service = escalate |
| `k8s-engineer` | One cluster's manifests. Cross-cluster / cross-repo Helm = escalate |
| `go-specialist` | One Go service's code. Cross-repo lib consistency = escalate |
| `frontend-specialist` | One app's UI. Cross-app design system audit = escalate |
| `devops-engineer` | One pipeline/infra unit. Cross-repo CI policy = escalate |
| `sre-engineer` | One service's SLOs. Cross-service error budget = escalate |
| `cloud-engineer` | One account/region. Cross-account IAM policy = escalate |

---

## Why This Exists

The routing system makes a single decision at session start (auctioneer auction). Once a specialist is assigned, no automatic mechanism re-evaluates scope as the conversation evolves. This skill closes that gap by making each specialist responsible for detecting when the conversation has outgrown their domain.

**Anti-pattern this prevents:**
- Session starts: `fix PGDATA path in Helm chart` → `backend-specialist` assigned ✅
- Conversation evolves: `check how Ingress is configured in neighboring repos` → `backend-specialist` keeps answering ❌
- With this skill: `backend-specialist` detects "neighboring repos" → escalates to orchestrator ✅

---

## Integration Notes

This skill is intentionally lightweight — it adds one silent check per turn with no token overhead when scope is clean. The escalation path is explicit and hands full context to the orchestrator, preventing information loss during the handoff.
