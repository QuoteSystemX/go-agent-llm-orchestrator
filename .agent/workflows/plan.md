---
description: Create project plan using project-planner agent. No code writing - only plan file generation.
---

# /plan - Project Planning Mode

$ARGUMENTS

---

## 🔴 CRITICAL RULES

1. **NO CODE WRITING** - This command creates plan file only
2. **Use project-planner agent** - NOT Antigravity Agent's native Plan mode
3. **Socratic Gate** - Ask clarifying questions before planning
4. **Dynamic Naming** - Plan file named based on task

---

## Task

Use the `project-planner` agent with this context:

```
CONTEXT:
- User Request: $ARGUMENTS
- Mode: PLANNING ONLY (no code)
- Output: tasks/YYYY-MM-DD-PLAN-{task-slug}.md (dynamic naming)

NAMING RULES:
1. Use current date: YYYY-MM-DD
2. Extract 2-3 key words from request
3. Lowercase, hyphen-separated
4. Max 30 characters
5. Example: "e-commerce cart" → 2026-04-22-PLAN-ecommerce-cart.md

RULES:
1. Follow project-planner.md Phase -1 (Context Check)
2. Follow project-planner.md Phase 0 (Socratic Gate)
3. Create YYYY-MM-DD-PLAN-{slug}.md in tasks/ with breakdown
4. DO NOT write any code files
5. REPORT the exact file name created
```

---

## Expected Output

| Deliverable | Location |
|-------------|----------|
| Project Plan | `tasks/YYYY-MM-DD-PLAN-{task-slug}.md` |
| Task Breakdown | Inside plan file |
| Agent Assignments | Inside plan file |
| Verification Checklist | Phase X in plan file |

---

## After Planning

Tell user:
```
[OK] Plan created: tasks/YYYY-MM-DD-PLAN-{slug}.md

Next steps:
- Review the plan
- Run `/create` to start implementation
- Or modify plan manually
```

---

## Naming Examples

| Request | Plan File |
|---------|-----------|
| `/plan e-commerce site with cart` | `tasks/2026-04-22-PLAN-ecommerce-cart.md` |
| `/plan mobile app for fitness` | `tasks/2026-04-22-PLAN-fitness-app.md` |
| `/plan add dark mode feature` | `tasks/2026-04-22-PLAN-dark-mode.md` |
| `/plan fix authentication bug` | `tasks/2026-04-22-PLAN-auth-fix.md` |
| `/plan SaaS dashboard` | `tasks/2026-04-22-PLAN-saas-dashboard.md` |

---

## Usage

```
/plan e-commerce site with cart
/plan mobile app for fitness tracking
/plan SaaS dashboard with analytics
```
