---
name: triage
description: Classify, prioritize, and assign incoming issues, security findings, or documentation drift.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
version: 1.0.0
---

# Triage Skill

> Efficiently categorize, prioritize, and route incoming tasks, system alerts, and security scan findings to maintain repository health and stability.

## 🎯 When to Use This Skill

- **Trigger**: Handling incoming security alerts from `security_scan.py` or vulnerability scanners.
- **Trigger**: Organizing tasks, tickets, or user-queued messages in `tasks/INBOX.md`.
- **Trigger**: Reviewing documentation drift reports from `drift_detector.py`.
- **Trigger**: Classifying runtime errors, logs, or system exceptions to assign them to correct domain specialists.

---

## 📋 Triage Procedures & Rules

### 1. Severity Classification

Every triage agent **must** evaluate and classify incoming issues into one of these categories:
- **CRITICAL**: Immediate action required. Potential data loss, credential leak, or production deployment block. (e.g., hardcoded secret, remote execution vulnerability).
- **HIGH**: Needs attention before the next deploy. Broken core business flows, missing tests, or security warnings.
- **MEDIUM**: Important but not blocking. Minor code debt, architectural suggestions, or documentation drift.
- **LOW**: Minor optimization suggestions, spelling fixes, or formatting requests.

### 2. Issue Routing & Ownership

Once classified, route the task to the most appropriate agent:
- **Rule 1**: Infra / Runtime issues **must** be routed to `@platform-lead` or `@sre-engineer`.
- **Rule 2**: Security findings **must** be routed to `@security-auditor` or `@risk-manager`.
- **Rule 3**: Core business logic and API issues **should** be routed to `@backend-specialist`.
- **Rule 4**: UI/UX and styling issues **should** be routed to `@frontend-specialist`.

### 3. Verification & Resolution Loop

- **Rule 5**: Always update task status to `in-progress` when starting work.
- **Rule 6**: Mark as `closed` or `completed` only after verifying that the fix passes all unit and integration tests.

---

## 💻 Code Examples & Routing Templates

### Severity Mapping Table

| Alert Source | Diagnostic Signal | Classified Severity | Target Agent |
|---|---|---|---|
| `security_scan.py` | Found private key | 🔴 CRITICAL | `@security-auditor` |
| `test_runner.py` | Core API test failed | 🟠 HIGH | `@backend-specialist` |
| `drift_detector.py` | 5 files not in docs | 🟡 MEDIUM | `@documentation-writer` |
| `lint_runner.py` | Unused variable warning | 🟢 LOW | `@debugger` |

### Triage Log Pattern

```json
{
  "event": "issue_triaged",
  "severity": "HIGH",
  "assigned_agent": "backend-specialist",
  "ref": "tasks/INBOX.md#L45"
}
```

---

## ❌ Anti-Patterns & Pitfalls to Avoid

- **Anti-Pattern (Silent Ignorance)**: Don't ignore low-severity warnings. They accumulate technical debt and lower the health score.
- **Anti-Pattern (Wrong Routing)**: Avoid assigning security audits to frontend agents. Security issues require specialised agents.
- **Anti-Pattern (Incomplete Resolution)**: Never mark a ticket as fixed without running `status_report.py` and `checklist.py`.
- **Anti-Pattern (Duplicate Triage)**: Avoid re-triaging an already assigned issue unless the domain changes (drift).
