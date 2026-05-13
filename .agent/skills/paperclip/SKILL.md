---
name: paperclip
description: The core operational heartbeat for QuoteSystemX leadership agents. Defines the cycle of waking up, analyzing tasks, delegating, and reporting progress.
version: 1.1.0
---

# 📎 Paperclip Heartbeat (Core)

This skill defines the standard operational cycle for **all** agents at QuoteSystemX.

## 💓 The Heartbeat Cycle

Every time you start a task or a new session (heartbeat), follow these steps:

### 1. Situational Awareness
- **Sync**: Check the current task status and any recent comments.
- **Context**: Read `.agent/bus/` for relevant data from other agents.

### 2. Implementation & Execution
- **Lenses**: Apply the relevant Domain Lenses (see below) during analysis.
- **Action**: Perform the work assigned to you.
- **Verify**: Run tests or manual checks to ensure quality.

## 🔍 Domain Lens Library

When performing your analysis, pick the lenses that match your role category:

### 👑 Management Lenses
- **Complexity-to-Value**: Is this the simplest way to deliver the most value?
- **Risk Mitigation**: What is the worst-case scenario and how do we prevent it?
- **Roadmap Alignment**: Does this fit our long-term technical vision?

### 🛠 Engineering Lenses
- **Performance**: Will this scale under high load (1k+ trades/sec)?
- **Security-by-Default**: Are inputs validated? Is auth required?
- **Testability**: Can this be unit tested without complex mocks?
- **Clean Code**: Is it concise, self-documenting, and DRY?

### 🧪 QA & Verification Lenses
- **Edge Cases**: What happens at the boundaries (zero balance, 5xx error)?
- **Regression**: Does this change break existing functionality?
- **UX Flow**: Is the user journey smooth and logical?

### 🚀 Infrastructure Lenses
- **Rollback Safety**: Can we undo this change in < 30 seconds?
- **Observability**: Is there logging/tracing for this new logic?
- **Cost Efficiency**: Are we over-provisioning resources?

### 3. Durable Progress (MANDATORY)
Before exiting, you MUST leave a summary comment with this exact structure:

```markdown
### Progress Report
- **Status**: [What changed]
- **Blockers**: [What is stopping you, who owns it, what action is needed]
- **Next Action**: [What should happen next and who is responsible]
```

### 4. Session Finalization
- Update the task metadata (e.g., `status: in_progress` or `status: review`).
- If delegating, create a child task.

## 📝 Rules
- Never exit a heartbeat without a progress report.
- Mark blocked work explicitly with owner and action.

## Changelog

- **1.1.0** (2026-05-13): Initial version
